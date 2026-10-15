from datetime import date

import pytest

from app.ledger import DecisionRecord, Mention
from app.ledger_store import InMemoryLedger
from app.matcher import Matcher, fake_embed
from app.memory import MemoryService


class Clock:
    def __init__(self, d):
        self.d = d

    def __call__(self):
        return self.d


def _service():
    clock = Clock(date(2026, 10, 15))
    ledger = InMemoryLedger()
    return MemoryService(ledger, Matcher(fake_embed), today_fn=clock), ledger, clock


BACKEND = dict(title="Rewrite the backend or keep shipping features",
               options=["rewrite backend", "keep shipping"],
               worries=["afraid of choosing wrong"])
BACKEND_REWORDED = dict(title="Should I rewrite the backend now or keep shipping?",
                        options=["rewrite", "keep shipping features"],
                        worries=["worried about losing momentum"])


def test_record_round_trips_through_dict():
    rec = DecisionRecord(user_id="u", title="t", worries=["w"], seeded=True,
                         mentions=[Mention("s1", "2026-10-01", "n")])
    again = DecisionRecord.from_dict(rec.to_dict())
    assert again == rec


def test_from_dict_ignores_unknown_fields():
    d = DecisionRecord(user_id="u", title="t").to_dict()
    d["something_new"] = 1
    assert DecisionRecord.from_dict(d).title == "t"


def test_first_session_creates_one_record_and_no_memory_block():
    svc, ledger, _ = _service()
    ctx = svc.prepare("u1", "s1", **BACKEND)
    assert ctx.facts.times_raised == 1
    assert ctx.prompt_block == ""
    assert len(ledger.list_for_user("u1")) == 1


def test_returning_decision_is_counted_not_duplicated():
    svc, ledger, clock = _service()
    first = svc.prepare("u1", "s1", **BACKEND)
    clock.d = date(2026, 10, 22)
    second = svc.prepare("u1", "s2", **BACKEND_REWORDED)
    assert second.decision_id == first.decision_id
    assert second.facts.times_raised == 2
    assert second.facts.stance == "name_the_loop"
    assert second.facts.days_open == 7
    assert len(ledger.list_for_user("u1")) == 1
    rec = ledger.get("u1", first.decision_id)
    assert "worried about losing momentum" in rec.worries      # new worry merged in
    assert "afraid of choosing wrong" in rec.worries           # old worry kept


def test_third_return_asks_permission_before_being_direct():
    svc, _, clock = _service()
    svc.prepare("u1", "s1", **BACKEND)
    svc.prepare("u1", "s2", **BACKEND_REWORDED)
    third = svc.prepare("u1", "s3", **BACKEND)
    assert third.facts.times_raised == 3
    assert third.facts.stance == "ask_permission_to_be_direct"
    fourth = svc.prepare("u1", "s4", **BACKEND, direct_opt_in=True)
    assert fourth.facts.stance == "direct"


def test_commit_then_return_remembers_the_users_own_words():
    svc, _, clock = _service()
    first = svc.prepare("u1", "s1", **BACKEND)
    svc.commit("u1", first.decision_id, "parked", "wait until after launch",
               "write down what would change my mind", "2026-10-20")
    clock.d = date(2026, 10, 25)
    again = svc.prepare("u1", "s2", **BACKEND_REWORDED)
    assert again.facts.revisit_overdue is True
    assert "wait until after launch" in again.prompt_block
    assert again.payload["previous"]["kind"] == "parked"


def test_similar_worry_in_a_different_decision_becomes_an_echo():
    svc, _, clock = _service()
    hire = svc.prepare("u1", "s1", title="Hire a contractor or do everything myself",
                       options=["hire contractor", "do it myself"],
                       worries=["afraid of choosing the wrong person", "afraid of choosing wrong"])
    svc.commit("u1", hire.decision_id, "decided", "try a smaller version first",
               "email two contractors about a paid trial week")
    clock.d = date(2026, 11, 5)
    ctx = svc.prepare("u1", "s2", **BACKEND)
    assert ctx.facts.times_raised == 1
    assert len(ctx.facts.echoes) == 1
    assert "try a smaller version first" in ctx.prompt_block
    assert ctx.payload["echoes"][0]["days_ago"] == 21


def test_one_users_history_never_reaches_another_user():
    svc, _, _ = _service()
    other = svc.prepare("alice", "s1", title="Hire a contractor or do everything myself",
                        options=["hire contractor"], worries=["afraid of choosing wrong"])
    svc.commit("alice", other.decision_id, "decided", "start small")
    mine = svc.prepare("bob", "s1", **BACKEND)
    assert mine.facts.echoes == []
    assert mine.prompt_block == ""


def test_parked_needs_a_revisit_date():
    svc, _, _ = _service()
    ctx = svc.prepare("u1", "s1", **BACKEND)
    with pytest.raises(ValueError):
        svc.commit("u1", ctx.decision_id, "parked", "later")


def test_need_more_info_is_a_valid_outcome_without_a_date():
    svc, ledger, _ = _service()
    ctx = svc.prepare("u1", "s1", **BACKEND)
    svc.commit("u1", ctx.decision_id, "need_more_info", "I need two customer calls first")
    assert ledger.get("u1", ctx.decision_id).conclusion_kind == "need_more_info"


def test_bad_kind_and_unknown_decision_are_rejected():
    svc, _, _ = _service()
    ctx = svc.prepare("u1", "s1", **BACKEND)
    with pytest.raises(ValueError):
        svc.commit("u1", ctx.decision_id, "maybe", "x")
    with pytest.raises(KeyError):
        svc.commit("u1", "nope", "decided", "x")


def test_outcome_note_is_saved_and_echoed_later():
    svc, _, clock = _service()
    hire = svc.prepare("u1", "s1", title="Hire a contractor or do everything myself",
                       options=["hire contractor"], worries=["afraid of choosing wrong"])
    svc.commit("u1", hire.decision_id, "decided", "start small")
    svc.record_outcome("u1", hire.decision_id, "the trial week went fine")
    clock.d = date(2026, 11, 5)
    ctx = svc.prepare("u1", "s2", **BACKEND)
    assert "the trial week went fine" in ctx.prompt_block


def test_unsafe_user_ids_are_refused():
    svc, _, _ = _service()
    for bad in ("", "a/b", "x" * 200):
        with pytest.raises(ValueError):
            svc.prepare(bad, "s1", **BACKEND)


def test_returning_decision_can_still_echo_a_different_past_decision():
    svc, _, clock = _service()
    hire = svc.prepare("u1", "s1", title="Hire a contractor or do everything myself",
                       options=["hire contractor"],
                       worries=["afraid of choosing the wrong person", "afraid of choosing wrong"])
    svc.commit("u1", hire.decision_id, "decided", "try a smaller version first")
    first = svc.prepare("u1", "s2", title="Rewrite the backend or keep shipping features",
                        options=["rewrite backend"], worries=["momentum", "3-month rewrite"])
    clock.d = date(2026, 11, 5)
    again = svc.prepare("u1", "s3", title="Should I rewrite the backend now or keep shipping?",
                        options=["rewrite"], worries=["afraid of choosing wrong"])
    assert again.decision_id == first.decision_id and again.facts.times_raised == 2
    assert [e.title for e in again.facts.echoes] == ["Hire a contractor or do everything myself"]
