"""Pydantic models for the HTTP API and for structured model output.

LLM-facing models avoid defaults and Literal types on purpose: Gemini's
response_schema is most reliable with plain str/list fields. We validate in session.py.
"""
from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, Field


# --- Structured output from Gemini ------------------------------------------------
class ExtractionOut(BaseModel):
    decision: str
    options: list[str]
    worries: list[str]


class TurnOut(BaseModel):
    type: str          # "question" or "observation"
    text: str


# --- HTTP request bodies (field names match index.html) ----------------------------
class StartIn(BaseModel):
    dump: str = Field(min_length=1)
    direct_opt_in: bool = False


class AnswerIn(BaseModel):
    answer: str = Field(min_length=1)


class CommitIn(BaseModel):
    conclusion: str = Field(min_length=1)
    conclusion_kind: Literal["decided", "need_more_info", "parked"]
    next_step: str = ""
    revisit_date: Optional[date] = None
