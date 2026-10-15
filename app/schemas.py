from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


class Turn(BaseModel):
    """A single AI turn returned to the browser."""
    type: Literal["question", "observation", "offer_commit"]
    text: str
    decision_ids: list[str] = Field(default_factory=list)  # IDs of echoed past decisions


class Extraction(BaseModel):
    """Structured fields the LLM extracts from the user's dump."""
    decision: str       # one-line statement of what is being decided
    worries: list[str]  # fears / concerns the user expressed
    options: list[str]  # options the user mentioned (never invented)


class Commit(BaseModel):
    """What the user resolves at the end of a session."""
    conclusion: str
    conclusion_kind: Literal["decided", "need_more_info", "parked"]
    next_step: str
    revisit_date: Optional[date] = None


class Decision(BaseModel):
    """One ledger entry (persisted to Firestore or memory store)."""
    id: str
    created_at: str                      # ISO-8601
    dump: str                            # raw user dump
    worries: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    conclusion: Optional[str] = None
    next_step: Optional[str] = None
    revisit_date: Optional[date] = None
    embedding: Optional[list[float]] = None
