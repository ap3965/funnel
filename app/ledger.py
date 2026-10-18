"""Ledger data model: one DecisionRecord per decision a user is carrying.

Plain dataclasses (no pydantic) so the model has no dependencies and
serialises cleanly to Firestore via to_dict()/from_dict().
Dates are ISO strings (YYYY-MM-DD).
"""
from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from typing import Optional

# "need_more_info" and "parked" are valid outcomes, not failures.
CONCLUSION_KINDS = ("decided", "need_more_info", "parked")
# The user's own next step: open -> done / not_yet / dropped. Never a score, never a streak.
STEP_STATUSES = ("open", "done", "not_yet", "dropped")


def _today_iso() -> str:
    return date.today().isoformat()


@dataclass
class Mention:
    """One time the user raised this decision (the first mention is creation)."""
    session_id: str
    at: str
    note: str = ""


@dataclass
class DecisionRecord:
    user_id: str
    title: str
    worries: list = field(default_factory=list)   # worries the user named
    options: list = field(default_factory=list)   # options the USER named
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    created_at: str = field(default_factory=_today_iso)
    mentions: list = field(default_factory=list)  # list[Mention]
    conclusion_kind: Optional[str] = None         # decided | need_more_info | parked
    conclusion: Optional[str] = None              # the user's own words
    next_step: Optional[str] = None               # the user's own words
    step_status: Optional[str] = None             # open | done | not_yet | dropped (None = no next step)
    step_updated_at: Optional[str] = None
    revisit_date: Optional[str] = None
    outcome_note: Optional[str] = None            # filled in later, after it happened
    seeded: bool = False                          # True = demo history, shown as such in the UI
    topic_embedding: Optional[list] = None
    worry_embedding: Optional[list] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "DecisionRecord":
        known = {f.name for f in fields(cls)}
        d = {k: v for k, v in dict(d).items() if k in known}
        d["mentions"] = [Mention(**m) if isinstance(m, dict) else m
                         for m in d.get("mentions", [])]
        return cls(**d)


def topic_text(rec: DecisionRecord) -> str:
    """Text used to decide whether two records are the SAME decision."""
    opts = "; ".join(rec.options)
    return f"{rec.title}. Options: {opts}" if opts else rec.title


def worry_text(rec: DecisionRecord) -> str:
    """Text used to find an ECHO: a different decision with a similar worry."""
    return "; ".join(rec.worries) if rec.worries else rec.title
