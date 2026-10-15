"""MemoryService: the ONE place your session code talks to memory.

    ctx = memory.prepare(user_id, session_id, title, options, worries)
        -> ctx.prompt_block   append this to the interrogator system prompt
        -> ctx.payload        send this to the UI for the "what I remembered" card
        -> ctx.decision_id    keep it for the commit step

    memory.commit(user_id, decision_id, kind, conclusion, next_step, revisit_date)
    memory.record_outcome(user_id, decision_id, note)   # later, after it happened

Everything here is plain code. The LLM only ever sees ctx.prompt_block.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Callable, Optional

from .ledger import CONCLUSION_KINDS, DecisionRecord, Mention
from .logs import log_event
from .patterns import Facts, compute_facts, render_for_prompt


@dataclass
class MemoryContext:
    decision_id: str
    facts: Facts
    prompt_block: str
    payload: dict


def _merge_unique(existing: list, new: list) -> list:
    seen = {x.strip().lower() for x in existing}
    merged = list(existing)
    for item in new:
        key = item.strip().lower()
        if key and key not in seen:
            merged.append(item.strip())
            seen.add(key)
    return merged


class MemoryService:
    def __init__(self, ledger, matcher, today_fn: Callable = date.today) -> None:
        self.ledger = ledger
        self.matcher = matcher
        self.today_fn = today_fn

    def prepare(self, user_id: str, session_id: str, title: str,
                options: Optional[list] = None, worries: Optional[list] = None,
                direct_opt_in: bool = False) -> MemoryContext:
        today = self.today_fn()
        history = self.ledger.list_for_user(user_id)   # this user only

        draft = DecisionRecord(user_id=user_id, title=title.strip(),
                               options=list(options or []), worries=list(worries or []),
                               created_at=today.isoformat())
        try:
            self.matcher.embed_record(draft)
        except Exception as exc:        # the session must still work without memory
            log_event("embed_failed", error=type(exc).__name__)

        same = self.matcher.find_same(draft, history)
        if same:
            current = same.record
            current.options = _merge_unique(current.options, draft.options)
            current.worries = _merge_unique(current.worries, draft.worries)
            current.mentions.append(Mention(session_id, today.isoformat()))
            exclude = {current.id}
        else:
            current = draft
            current.mentions.append(Mention(session_id, today.isoformat()))
            exclude = set()

        # Echo on what the user feels NOW (the fresh draft), not on the stored record's old worries.
        echoes = self.matcher.find_echoes(draft, history, exclude_ids=exclude)
        facts = compute_facts(current, echoes, today, direct_opt_in)
        self.ledger.save(current)
        return MemoryContext(current.id, facts, render_for_prompt(facts),
                             self._payload(current, facts))

    def commit(self, user_id: str, decision_id: str, kind: str, conclusion: str = "",
               next_step: str = "", revisit_date: Optional[str] = None) -> DecisionRecord:
        if kind not in CONCLUSION_KINDS:
            raise ValueError(f"kind must be one of {CONCLUSION_KINDS}")
        if kind == "parked" and not revisit_date:
            raise ValueError("a parked decision needs a revisit date")
        rec = self.ledger.get(user_id, decision_id)
        if rec is None:
            raise KeyError("unknown decision")
        rec.conclusion_kind = kind
        rec.conclusion = conclusion.strip() or None
        rec.next_step = next_step.strip() or None
        rec.revisit_date = revisit_date
        self.ledger.save(rec)
        return rec

    def record_outcome(self, user_id: str, decision_id: str, note: str) -> DecisionRecord:
        rec = self.ledger.get(user_id, decision_id)
        if rec is None:
            raise KeyError("unknown decision")
        rec.outcome_note = note.strip() or None
        self.ledger.save(rec)
        return rec

    def list_for_ui(self, user_id: str) -> list:
        """The ledger overlay. Field names match what index.html reads."""
        recs = sorted(self.ledger.list_for_user(user_id), key=lambda r: r.created_at, reverse=True)
        return [{"id": r.id, "created_at": r.created_at, "dump": r.title,
                 "conclusion": r.conclusion, "conclusion_kind": r.conclusion_kind,
                 "next_step": r.next_step, "revisit_date": r.revisit_date,
                 "seeded": r.seeded, "times_raised": len(r.mentions)} for r in recs]

    @staticmethod
    def _payload(rec: DecisionRecord, facts: Facts) -> dict:
        """JSON for the UI. Neutral wording: a timeline, not a scoreboard."""
        return {
            "decision_id": rec.id,
            "title": rec.title,
            "times_raised": facts.times_raised,
            "stance": facts.stance,
            "seeded": facts.used_seeded,
            "timeline": [{"date": m.at} for m in rec.mentions],
            "revisit_overdue": facts.revisit_overdue,
            "previous": ({"kind": facts.previous_conclusion_kind,
                          "conclusion": facts.previous_conclusion,
                          "next_step": facts.previous_next_step}
                         if facts.previous_conclusion_kind else None),
            "echoes": [{"title": e.title, "days_ago": e.days_ago, "worries": e.worries,
                        "conclusion": e.conclusion, "seeded": e.seeded}
                       for e in facts.echoes],
        }
