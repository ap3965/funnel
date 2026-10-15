"""
session.py — the turn loop.

Flow per turn:
  extract (first turn only) -> match past decisions -> compute facts ->
  build question via LLM -> guard -> return Turn
"""

from __future__ import annotations

import logging
from typing import Any

from app import llm, guard, facts, matcher
from app.prompts import (
    EXTRACTOR_SYSTEM, EXTRACTOR_USER_TMPL,
    INTERROGATOR_SYSTEM, INTERROGATOR_USER_TMPL,
    OBSERVATION_SYSTEM, OBSERVATION_USER_TMPL,
)
from app.schemas import Commit, Decision, Extraction, Turn
from app.store import get_store

logger = logging.getLogger("funnel.session")

# In-memory session context (lives for the request lifetime; state held by client)
# session_id -> {"decision_id": str, "history": [{"role":..,"content":..}], "turn_count": int}
_sessions: dict[str, dict[str, Any]] = {}

MAX_QUESTIONS = 6  # after which we offer a commit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _extract(dump: str) -> Extraction:
    msgs = [{"role": "user", "content": EXTRACTOR_USER_TMPL.format(dump=dump)}]
    return llm.generate_structured(EXTRACTOR_SYSTEM, msgs, Extraction)


def _build_context(session: dict) -> str:
    decision_id = session["decision_id"]
    store = get_store()
    d = store.get_decision(decision_id)
    if not d:
        return ""
    lines = [f"Decision: {d.dump}"]
    if d.worries:
        lines.append("Worries expressed: " + "; ".join(d.worries))
    if d.options:
        lines.append("Options mentioned: " + "; ".join(d.options))
    return "\n".join(lines)


def _make_question(context: str, user_answer: str, strict: bool = False) -> str:
    system = INTERROGATOR_SYSTEM
    if strict:
        system += "\n\nEXTRA STRICT: absolutely no advice or any imperative phrasing. One question only."
    msgs = [
        {"role": "user", "content": INTERROGATOR_USER_TMPL.format(
            context=context, user_answer=user_answer
        )}
    ]
    return llm.generate_text(system, msgs, temperature=0.7).strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def start_session(session_id: str, dump: str) -> Turn:
    """Called once with the user's raw dump. Creates the Decision in the store."""
    store = get_store()

    # Extract structure
    extraction = _extract(dump)

    # Embed the worries for future matching
    worry_text = " ".join(extraction.worries) if extraction.worries else dump
    try:
        embeddings = llm.embed([worry_text])
        embedding = embeddings[0] if embeddings else None
    except Exception:
        embedding = None

    # Create Decision record
    decision = Decision(
        id=store.new_id(),
        created_at=store.now_iso(),
        dump=dump,
        worries=extraction.worries,
        options=extraction.options,
        embedding=embedding,
    )
    store.save_decision(decision)

    # Check for similar past decisions
    all_past = [d for d in store.list_decisions() if d.id != decision.id]
    similar = matcher.find_similar(extraction.worries, embedding, all_past)
    similar_ids = [d.id for d in similar]

    # Possibly prepend an observation about recurrence
    recurrence_fact = facts.build_recurrence_fact(extraction.worries, all_past)
    if recurrence_fact and similar:
        obs_msgs = [{"role": "user", "content": OBSERVATION_USER_TMPL.format(fact=recurrence_fact)}]
        obs_text = llm.generate_text(OBSERVATION_SYSTEM, obs_msgs, temperature=0.5).strip()
        obs_clean = guard.guard_or_fallback(obs_text)
        # Return as observation turn (session will continue next call)
        _sessions[session_id] = {
            "decision_id": decision.id,
            "history": [{"role": "user", "content": dump}],
            "turn_count": 0,
            "pending_observation": True,
        }
        return Turn(type="observation", text=obs_clean, decision_ids=similar_ids)

    # Otherwise go straight to first question
    context = f"Decision: {dump}\nWorries: {', '.join(extraction.worries)}\nOptions: {', '.join(extraction.options)}"
    raw_q = _make_question(context, dump)
    clean_q = guard.guard_or_fallback(raw_q, retry_fn=lambda: _make_question(context, dump, strict=True))

    _sessions[session_id] = {
        "decision_id": decision.id,
        "history": [{"role": "user", "content": dump}],
        "turn_count": 1,
        "pending_observation": False,
    }
    return Turn(type="question", text=clean_q, decision_ids=similar_ids)


def next_turn(session_id: str, user_answer: str) -> Turn:
    """Called for every subsequent user answer."""
    session = _sessions.get(session_id)
    if not session:
        return Turn(type="question", text="Can you tell me a bit more about what you're deciding?", decision_ids=[])

    session["history"].append({"role": "user", "content": user_answer})
    session["turn_count"] += 1
    turn_count = session["turn_count"]

    # Offer commit after MAX_QUESTIONS
    if turn_count >= MAX_QUESTIONS:
        return Turn(
            type="offer_commit",
            text="It sounds like you've explored this well. Do you feel ready to name where you've landed — even if it's 'I need more time'?",
            decision_ids=[],
        )

    context = _build_context(session)
    raw_q = _make_question(context, user_answer)
    clean_q = guard.guard_or_fallback(raw_q, retry_fn=lambda: _make_question(context, user_answer, strict=True))

    return Turn(type="question", text=clean_q, decision_ids=[])


def commit_session(session_id: str, commit: Commit) -> Decision | None:
    """Saves the user's conclusion to the ledger."""
    session = _sessions.get(session_id)
    if not session:
        return None
    store = get_store()
    return store.update_commit(session["decision_id"], commit)
