"""
facts.py — pure code computations. No LLM calls here.
The AI only receives the pre-computed strings; it cannot hallucinate numbers.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas import Decision


def recurrence_count(worries: list[str], all_decisions: list[Decision]) -> int:
    """
    How many past decisions share at least one worry keyword with the current set?
    Keyword match: any worry word (≥4 chars) appears in a past decision's worries list.
    """
    if not worries:
        return 0
    current_keywords = {w.lower() for worry in worries for w in worry.split() if len(w) >= 4}
    count = 0
    for d in all_decisions:
        past_keywords = {w.lower() for worry in d.worries for w in worry.split() if len(w) >= 4}
        if current_keywords & past_keywords:
            count += 1
    return count


def days_since(decision: Decision) -> int:
    """Days elapsed since a decision was created."""
    created = datetime.fromisoformat(decision.created_at)
    now = datetime.now(timezone.utc)
    if created.tzinfo is None:
        created = created.replace(tzinfo=timezone.utc)
    return (now - created).days


def previous_outcome_summary(decision: Decision) -> str | None:
    """Returns a one-line human-readable outcome or None if not committed."""
    if not decision.conclusion:
        return None
    kind_label = {
        "decided": "decided",
        "need_more_info": "needed more info",
        "parked": "parked",
    }.get(str(decision.conclusion_kind if hasattr(decision, 'conclusion_kind') else "decided"), "concluded")
    return f"You {kind_label}: "{decision.conclusion}""


def build_recurrence_fact(current_worries: list[str], all_decisions: list[Decision]) -> str | None:
    """
    Returns a fact string for the Observation prompt, or None if nothing notable.
    Always based on code counts — never invented.
    """
    n = recurrence_count(current_worries, all_decisions)
    if n == 0:
        return None
    if n == 1:
        return f"A similar worry appeared in 1 earlier decision in your ledger."
    return f"A similar worry appeared in {n} earlier decisions in your ledger."
