"""The session loop: Dump -> Discover -> Decide -> Move.

SessionManager holds conversations in memory (so run Cloud Run with max-instances=1).
Anything worth keeping long-term is written to the ledger at start and at commit.
Nothing here imports a model SDK: the model is injected, so tests use a fake.
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Callable, Optional

from . import config
from .guard import check
from .logs import log_event
from .prompts import FALLBACK_QUESTIONS, INTERROGATOR_SYSTEM, RETRY_NOTE

MAX_ATTEMPTS = 3          # first try + two regenerations
MAX_TURNS = 30            # per session, to protect the quota
OFFER_COMMIT_AFTER = 6    # model turns before we offer to write a conclusion
OFFER_TEXT = ("It sounds like you've explored this well. Do you feel ready to name where "
              "you've landed, even if it's 'I need more time'?")
_KINDS = ("question", "observation")


@dataclass
class Session:
    id: str
    user_id: str
    decision_id: Optional[str]
    messages: list
    memory_block: str = ""
    memory_payload: Optional[dict] = None
    created: float = 0.0
    last_used: float = 0.0
    turns: int = 0
    fallback_count: int = 0
    committed: bool = False
    offered: bool = False


def _clean(text, limit: int) -> str:
    return " ".join(str(text or "").split())[:limit]


def _clean_list(items, limit: int = 160, max_items: int = 6) -> list:
    out = [_clean(i, limit) for i in (items or [])]
    return [i for i in out if i][:max_items]


class SessionManager:
    def __init__(self, llm, memory, clock: Callable = time.time,
                 ttl: int = config.SESSION_TTL_SECONDS,
                 max_sessions: int = config.MAX_SESSIONS) -> None:
        self.llm = llm
        self.memory = memory
        self.clock = clock
        self.ttl = ttl
        self.max_sessions = max_sessions
        self._sessions: dict = {}
        # Counters for the deck: "the guard blocked X of Y replies".
        self.stats = {"sessions_started": 0, "turns": 0, "guard_checked": 0,
                      "guard_rejected": 0, "guard_soft": 0, "guard_fallbacks": 0,
                      "commits": 0}

    # -- public API -------------------------------------------------------------
    def start(self, user_id: str, dump: str, direct_opt_in: bool = False) -> dict:
        dump = (dump or "").strip()
        if not dump:
            raise ValueError("Write a few sentences first. Messy is fine.")
        if len(dump) > config.MAX_DUMP_CHARS:
            raise ValueError(f"That is too long. Keep it under {config.MAX_DUMP_CHARS} characters.")
        self._purge()

        now = self.clock()
        sess = Session(id=uuid.uuid4().hex, user_id=user_id, decision_id=None,
                       messages=[{"role": "user", "text": dump}], created=now, last_used=now)

        extraction = self.llm.extract(dump)
        title = _clean(extraction.get("decision"), 120) or _clean(dump, 80)
        try:
            ctx = self.memory.prepare(user_id, sess.id, title,
                                      options=_clean_list(extraction.get("options")),
                                      worries=_clean_list(extraction.get("worries")),
                                      direct_opt_in=direct_opt_in)
            sess.decision_id = ctx.decision_id
            sess.memory_block = ctx.prompt_block
            sess.memory_payload = ctx.payload
        except ValueError:
            raise                                     # bad user id: tell the caller
        except Exception as exc:                      # memory down: the session still works
            log_event("memory_unavailable", error=type(exc).__name__)

        try:
            turn = self._next_turn(sess)
        except Exception:
            if sess.decision_id:                    # do not leave a half-created ledger entry
                try:
                    self.memory.discard_session(user_id, sess.decision_id, sess.id)
                except Exception as exc:
                    log_event("discard_failed", error=type(exc).__name__)
            raise
        self._sessions[sess.id] = sess
        self.stats["sessions_started"] += 1
        log_event("session_started", returning=bool(sess.memory_block))
        return {"session_id": sess.id, "turn": turn, "memory": sess.memory_payload}

    def answer(self, session_id: str, text: str) -> dict:
        sess = self._get(session_id)
        text = (text or "").strip()
        if not text:
            raise ValueError("Write an answer first.")
        if len(text) > config.MAX_ANSWER_CHARS:
            raise ValueError(f"That is too long. Keep it under {config.MAX_ANSWER_CHARS} characters.")
        if sess.turns >= MAX_TURNS:
            raise ValueError("This session has reached its limit. Save your decision or start again.")
        sess.messages.append({"role": "user", "text": text})
        if sess.turns >= OFFER_COMMIT_AFTER and not sess.offered:
            sess.offered = True                       # offered once; the user may keep going
            return {"turn": {"type": "offer_commit", "text": OFFER_TEXT}}
        return {"turn": self._next_turn(sess)}

    def commit(self, session_id: str, kind: str, conclusion: str = "",
               next_step: str = "", revisit_date: Optional[str] = None) -> dict:
        sess = self._get(session_id)
        if not sess.decision_id:
            raise RuntimeError("Saving is unavailable right now. Copy your conclusion somewhere safe and try again.")
        rec = self.memory.commit(sess.user_id, sess.decision_id, kind,
                                 _clean(conclusion, config.MAX_FIELD_CHARS),
                                 _clean(next_step, config.MAX_FIELD_CHARS), revisit_date)
        sess.committed = True
        self.stats["commits"] += 1
        log_event("decision_committed", kind=kind)
        return {"saved": True, "decision_id": rec.id, "kind": rec.conclusion_kind,
                "revisit_date": rec.revisit_date}

    def decisions(self, user_id: str) -> list:
        return self.memory.list_for_ui(user_id)

    # -- internals ----------------------------------------------------------------
    def _get(self, session_id: str) -> Session:
        sess = self._sessions.get(session_id)
        if sess is None or self.clock() - sess.last_used > self.ttl:
            self._sessions.pop(session_id, None)
            raise KeyError("session expired")
        sess.last_used = self.clock()
        return sess

    def _purge(self) -> None:
        now = self.clock()
        for sid in [s for s, v in self._sessions.items() if now - v.last_used > self.ttl]:
            del self._sessions[sid]
        while len(self._sessions) >= self.max_sessions:
            oldest = min(self._sessions.values(), key=lambda v: v.last_used)
            del self._sessions[oldest.id]

    def _next_turn(self, sess: Session) -> dict:
        system = INTERROGATOR_SYSTEM
        if sess.memory_block:
            system += "\n\n" + sess.memory_block
        note = ""
        for attempt in range(1, MAX_ATTEMPTS + 1):
            raw = self.llm.next_turn(system + note, sess.messages)
            text = _clean(raw.get("text"), 600)
            kind = raw.get("type") if raw.get("type") in _KINDS else None
            verdict = check(text, kind)
            self.stats["guard_checked"] += 1
            if verdict.soft:
                self.stats["guard_soft"] += 1
                log_event("guard_soft", reasons=verdict.soft)
            if verdict.ok:
                turn = {"type": kind or ("question" if "?" in text else "observation"),
                        "text": text}
                return self._record(sess, turn)
            self.stats["guard_rejected"] += 1
            log_event("guard_rejected", attempt=attempt, reasons=verdict.hard, model_text=text[:300])
            note = RETRY_NOTE.format(reasons="; ".join(verdict.hard))

        self.stats["guard_fallbacks"] += 1
        text = FALLBACK_QUESTIONS[sess.fallback_count % len(FALLBACK_QUESTIONS)]
        sess.fallback_count += 1
        log_event("guard_fallback")
        return self._record(sess, {"type": "question", "text": text})

    def _record(self, sess: Session, turn: dict) -> dict:
        sess.messages.append({"role": "model", "text": turn["text"]})
        sess.turns += 1
        self.stats["turns"] += 1
        return turn
