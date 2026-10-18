from datetime import date

import pytest

from app import config
from app.ledger_store import InMemoryLedger
from app.matcher import Matcher, fake_embed
from app.memory import MemoryService
from app.session import MAX_TURNS, OFFER_COMMIT_AFTER, SessionManager


class FakeLLM:
    """Scripted model. `turns` is a list of dicts (or Exceptions) returned in order."""

    def __init__(self, turns=None, extraction=None):
        self.turns = list(turns or [])
        self.extraction = extraction or {"decision": "Rewrite the backend or keep shipping features",
                                         "options": ["rewrite backend", "keep shipping"],
                                         "worries": ["afraid of choosing wrong"]}
        self.systems, self.histories = [], []
        self.commit_result = {"conclusion_kind": "decided", "conclusion": "keep shipping for 6 weeks",
                              "next_step": "write three prices tomorrow at 10am", "revisit_date": "2026-11-30"}
        self.commit_calls = []

    def extract_commit(self, text, today_iso):
        self.commit_calls.append((text, today_iso))
        return dict(self.commit_result)

    def extract(self, dump):
        return dict(self.extraction)

    def next_turn(self, system, messages):
        self.systems.append(system)
        self.histories.append([dict(m) for m in messages])
        item = self.turns.pop(0) if self.turns else {"type": "question", "text": "What feels hardest about this?"}
        if isinstance(item, Exception):
            raise item
        return item

    def embed(self, texts):
        return fake_embed(texts)


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _make(turns=None, **kw):
    llm = FakeLLM(turns)
    ledger = InMemoryLedger()
    memory = MemoryService(ledger, Matcher(fake_embed), today_fn=lambda: date(2026, 10, 15))
    clock = Clock()
    return SessionManager(llm, memory, clock=clock, **kw), llm, ledger, memory, clock


Q = {"type": "question", "text": "What would 'wrong' look like here?"}
ADVICE = {"type": "observation", "text": "You should rewrite it after launch."}


def test_start_returns_a_question_and_a_session():
    mgr, llm, ledger, _, _ = _make([Q])
    out = mgr.start("u1", "I can't decide whether to rewrite the backend.")
    assert out["turn"]["text"] == Q["text"]
    assert out["memory"]["times_raised"] == 1 and out["memory"]["echoes"] == []
    assert out["session_id"]
    assert llm.histories[0] == [{"role": "user", "text": "I can't decide whether to rewrite the backend."}]
    assert len(ledger.list_for_user("u1")) == 1


def test_conversation_alternates_user_and_model():
    mgr, llm, *_ = _make([Q, Q])
    sid = mgr.start("u1", "dump")["session_id"]
    mgr.answer(sid, "I think it is fear.")
    roles = [m["role"] for m in llm.histories[1]]
    assert roles == ["user", "model", "user"]


def test_guard_rejects_advice_and_regenerates():
    mgr, llm, *_ = _make([ADVICE, Q])
    out = mgr.start("u1", "dump")
    assert out["turn"]["text"] == Q["text"]
    assert mgr.stats["guard_checked"] == 2 and mgr.stats["guard_rejected"] == 1
    assert "WAS REJECTED" in llm.systems[1] and "WAS REJECTED" not in llm.systems[0]


def test_three_bad_replies_fall_back_to_a_safe_question():
    mgr, llm, *_ = _make([ADVICE, ADVICE, ADVICE])
    out = mgr.start("u1", "dump")
    assert out["turn"]["type"] == "question" and out["turn"]["text"].endswith("?")
    assert mgr.stats["guard_fallbacks"] == 1 and mgr.stats["guard_rejected"] == 3


def test_unknown_type_is_normalised():
    mgr, *_ = _make([{"type": "banana", "text": "What is the cost of waiting?"}])
    assert mgr.start("u1", "dump")["turn"]["type"] == "question"


def test_returning_user_gets_memory_in_the_prompt():
    mgr, llm, ledger, memory, _ = _make([Q, Q])
    # an earlier, concluded decision with a similar worry
    past = memory.prepare("u1", "old", "Hire a contractor or do everything myself",
                          ["hire contractor"], ["afraid of choosing the wrong person", "afraid of choosing wrong"])
    memory.commit("u1", past.decision_id, "decided", "try a smaller version first")
    out = mgr.start("u1", "dump")
    assert "MEMORY FACTS (counted by code" in llm.systems[0] and "try a smaller version first" in llm.systems[0]
    assert out["memory"]["echoes"][0]["title"].startswith("Hire a contractor")


def test_first_time_user_prompt_has_no_memory_block():
    mgr, llm, *_ = _make([Q])
    mgr.start("u1", "dump")
    assert "MEMORY FACTS (counted by code" not in llm.systems[0]


def test_commit_saves_the_users_own_words():
    mgr, _, ledger, *_ = _make([Q])
    out = mgr.start("u1", "dump")
    res = mgr.commit(out["session_id"], "decided", "ship first", "Tomorrow 10am, write three prices", "2026-10-30")
    rec = ledger.get("u1", res["decision_id"])
    assert rec.conclusion == "ship first" and rec.next_step.startswith("Tomorrow")
    assert mgr.stats["commits"] == 1


def test_parked_without_a_date_is_refused():
    mgr, *_ = _make([Q])
    out = mgr.start("u1", "dump")
    with pytest.raises(ValueError):
        mgr.commit(out["session_id"], "parked", "later")


def test_unknown_or_expired_session():
    mgr, _, _, _, clock = _make([Q])
    with pytest.raises(KeyError):
        mgr.answer("nope", "hi")
    sid = mgr.start("u1", "dump")["session_id"]
    clock.t += config.SESSION_TTL_SECONDS + 1
    with pytest.raises(KeyError):
        mgr.answer(sid, "hi")


def test_input_validation():
    mgr, *_ = _make([Q])
    with pytest.raises(ValueError):
        mgr.start("u1", "   ")
    with pytest.raises(ValueError):
        mgr.start("u1", "x" * (config.MAX_DUMP_CHARS + 1))
    sid = mgr.start("u1", "dump")["session_id"]
    with pytest.raises(ValueError):
        mgr.answer(sid, "")
    with pytest.raises(ValueError):
        mgr.answer(sid, "x" * (config.MAX_ANSWER_CHARS + 1))


def test_bad_user_id_is_refused():
    mgr, *_ = _make([Q])
    with pytest.raises(ValueError):
        mgr.start("a/b", "dump")


def test_turn_cap():
    mgr, *_ = _make()
    sid = mgr.start("u1", "dump")["session_id"]
    with pytest.raises(ValueError):
        for _ in range(MAX_TURNS + 2):
            mgr.answer(sid, "ok")


def test_memory_failure_does_not_break_the_session():
    mgr, _, _, memory, _ = _make([Q])

    def boom(*a, **k):
        raise RuntimeError("firestore down")

    memory.prepare = boom
    out = mgr.start("u1", "dump")
    assert out["turn"]["text"] == Q["text"] and out["memory"] is None
    with pytest.raises(RuntimeError):
        mgr.commit(out["session_id"], "decided", "x")


def test_embedding_failure_still_saves_the_record():
    mgr, llm, ledger, memory, _ = _make([Q])

    def bad_embed(texts):
        raise RuntimeError("embedding service down")

    memory.matcher.embed_fn = bad_embed
    out = mgr.start("u1", "dump")
    assert out["turn"]["text"] == Q["text"]
    assert len(ledger.list_for_user("u1")) == 1


def test_llm_errors_propagate_to_the_caller():
    mgr, *_ = _make([RuntimeError("model unavailable")])
    with pytest.raises(RuntimeError):
        mgr.start("u1", "dump")


def test_session_cap_drops_the_oldest():
    mgr, _, _, _, clock = _make(max_sessions=2)
    ids = []
    for i in range(3):
        clock.t += 1
        ids.append(mgr.start("u1", f"dump {i}")["session_id"])
    with pytest.raises(KeyError):
        mgr.answer(ids[0], "hi")


def test_write_it_down_hint_never_replaces_a_question():
    mgr, llm, *_ = _make()
    sid = mgr.start("u1", "dump")["session_id"]
    turns = [mgr.answer(sid, f"a{i}")["turn"] for i in range(OFFER_COMMIT_AFTER + 2)]
    assert all(t["type"] == "question" and t["text"].endswith("?") for t in turns)   # always a real question
    assert sum(1 for t in turns if t.get("offer")) == 1                              # hinted once, softly
    assert len(llm.histories) == OFFER_COMMIT_AFTER + 3                              # the model was asked every time


def test_decisions_are_private_per_user_and_match_the_ui_shape():
    mgr, *_ = _make()
    mgr.start("alice", "dump")
    mgr.start("bob", "dump")
    rows = mgr.decisions("alice")
    assert len(rows) == 1
    assert set(rows[0]) >= {"id", "created_at", "dump", "conclusion", "conclusion_kind",
                            "revisit_date", "seeded"}
    assert mgr.decisions("nobody") == []


def test_failed_first_question_leaves_no_orphan_entry():
    mgr, _, ledger, *_ = _make([RuntimeError("model unavailable")])
    with pytest.raises(RuntimeError):
        mgr.start("u1", "dump")
    assert ledger.list_for_user("u1") == []


def test_failed_return_visit_keeps_the_earlier_history():
    mgr, llm, ledger, *_ = _make([Q, RuntimeError("model unavailable")])
    mgr.start("u1", "dump")
    with pytest.raises(RuntimeError):
        mgr.start("u1", "dump again")
    rec = ledger.list_for_user("u1")[0]
    assert len(rec.mentions) == 1


# ---- wrap-up from free text ------------------------------------------------------
def test_wrap_returns_a_proposal_and_saves_nothing():
    mgr, llm, ledger, *_ = _make([Q])
    sid = mgr.start("u1", "dump")["session_id"]
    prop = mgr.wrap(sid, "I'll keep shipping for 6 weeks. Tomorrow 10am I'll write three prices.")
    assert prop == {"conclusion_kind": "decided", "conclusion": "keep shipping for 6 weeks",
                    "next_step": "write three prices tomorrow at 10am", "revisit_date": "2026-11-30"}
    assert llm.commit_calls and ledger.list_for_user("u1")[0].conclusion is None


def test_wrap_cleans_up_bad_model_output():
    mgr, llm, *_ = _make([Q])
    sid = mgr.start("u1", "dump")["session_id"]
    llm.commit_result = {"conclusion_kind": "banana", "conclusion": "", "next_step": "", "revisit_date": "next friday"}
    prop = mgr.wrap(sid, "Honestly I just need to sleep on it.")
    assert prop["conclusion_kind"] == "decided"
    assert prop["conclusion"] == "Honestly I just need to sleep on it."      # falls back to their own words
    assert prop["next_step"] == "" and prop["revisit_date"] is None


def test_wrap_validation():
    mgr, *_ = _make([Q])
    sid = mgr.start("u1", "dump")["session_id"]
    with pytest.raises(ValueError):
        mgr.wrap(sid, "  ")
    with pytest.raises(ValueError):
        mgr.wrap(sid, "x" * (config.MAX_ANSWER_CHARS + 1))
    with pytest.raises(KeyError):
        mgr.wrap("nope", "hi")


# ---- next steps: status, check-in, "not yet" -------------------------------------
def _with_saved_step(turns=None):
    mgr, llm, ledger, memory, clock = _make(turns or [Q, Q])
    out = mgr.start("u1", "dump")
    res = mgr.commit(out["session_id"], "decided", "keep shipping", "write three prices tomorrow at 10am", "2026-11-30")
    return mgr, llm, ledger, memory, res["decision_id"]


def test_commit_with_a_next_step_marks_it_open():
    mgr, _, ledger, _, did = _with_saved_step()
    assert ledger.get("u1", did).step_status == "open"
    row = mgr.decisions("u1")[0]
    assert row["step_status"] == "open" and row["next_step"].startswith("write three prices")


def test_commit_without_a_next_step_has_no_status():
    mgr, _, ledger, *_ = _make([Q])
    out = mgr.start("u1", "dump")
    res = mgr.commit(out["session_id"], "need_more_info", "I need two customer calls first")
    assert ledger.get("u1", res["decision_id"]).step_status is None


def test_user_can_mark_their_step_done_or_dropped():
    mgr, _, ledger, _, did = _with_saved_step()
    assert mgr.set_step("u1", did, "done")["step_status"] == "done"
    assert mgr.set_step("u1", did, "dropped")["step_status"] == "dropped"
    with pytest.raises(ValueError):
        mgr.set_step("u1", did, "open")
    with pytest.raises(ValueError):
        mgr.set_step("u1", did, "banana")


def test_not_yet_opens_a_session_about_that_decision():
    mgr, llm, ledger, _, did = _with_saved_step([Q, Q])
    out = mgr.start_from_step("u1", did)
    assert out["turn"]["text"] == Q["text"] and out["memory"]["times_raised"] == 2
    system = llm.systems[-1]
    assert "write three prices tomorrow at 10am" in system            # the user's own next step, from memory
    assert 'My next step was: "write three prices tomorrow at 10am"' in llm.histories[-1][0]["text"]
    assert ledger.get("u1", did).step_status == "not_yet"
    assert len(ledger.list_for_user("u1")) == 1                        # same decision, not a duplicate
    # the new session is a normal session: it can be answered and committed
    sid = out["session_id"]
    assert mgr.answer(sid, "I got scared of the number.")["turn"]["type"] == "question"
    res = mgr.commit(sid, "decided", "go with flat pricing", "post it on Friday 5pm", "2026-12-01")
    assert res["decision_id"] == did and ledger.get("u1", did).step_status == "open"


def test_not_yet_failure_leaves_no_extra_mention():
    mgr, llm, ledger, _, did = _with_saved_step([Q, RuntimeError("model unavailable")])
    with pytest.raises(RuntimeError):
        mgr.start_from_step("u1", did)
    assert len(ledger.get("u1", did).mentions) == 1


def test_one_user_cannot_touch_anothers_steps():
    mgr, _, _, _, did = _with_saved_step([Q, Q])
    with pytest.raises(KeyError):
        mgr.set_step("bob", did, "done")
    with pytest.raises(KeyError):
        mgr.start_from_step("bob", did)


def test_not_yet_needs_a_next_step():
    mgr, _, _, _, _ = _make([Q])
    out = mgr.start("u1", "other dump")
    mgr.commit(out["session_id"], "need_more_info", "need info")
    row = [r for r in mgr.decisions("u1") if r["next_step"] is None][0]
    with pytest.raises(KeyError):
        mgr.start_from_step("u1", row["id"])
