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


def test_offer_commit_appears_once_after_enough_turns():
    mgr, llm, *_ = _make()
    sid = mgr.start("u1", "dump")["session_id"]
    types = [mgr.answer(sid, f"a{i}")["turn"]["type"] for i in range(OFFER_COMMIT_AFTER + 1)]
    assert types.count("offer_commit") == 1
    assert types.index("offer_commit") == OFFER_COMMIT_AFTER - 1


def test_decisions_are_private_per_user_and_match_the_ui_shape():
    mgr, *_ = _make()
    mgr.start("alice", "dump")
    mgr.start("bob", "dump")
    rows = mgr.decisions("alice")
    assert len(rows) == 1
    assert set(rows[0]) >= {"id", "created_at", "dump", "conclusion", "conclusion_kind",
                            "revisit_date", "seeded"}
    assert mgr.decisions("nobody") == []
