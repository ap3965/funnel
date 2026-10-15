"""Pattern layer. PLAIN CODE: it counts and reads back. It never interprets.

compute_facts(...)   -> Facts      (numbers and past words, nothing else)
render_for_prompt()  -> str        (block appended to the interrogator prompt)

The LLM only phrases these facts. If a claim is not in this block,
the interrogator must not make it.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

from .ledger import DecisionRecord

# Escalation by how many times THIS decision has been raised (including today):
#   1 -> neutral
#   2 -> name_the_loop              ("we've been here before; what's keeping it open?")
#   3+ -> ask_permission_to_be_direct, then direct once the user opts in
STANCES = ("neutral", "name_the_loop", "ask_permission_to_be_direct", "direct")


@dataclass
class Echo:
    title: str
    worries: list
    conclusion_kind: Optional[str]
    conclusion: Optional[str]
    next_step: Optional[str]
    outcome_note: Optional[str]
    days_ago: int
    similarity: float
    seeded: bool


@dataclass
class Facts:
    times_raised: int = 1
    first_seen: Optional[str] = None
    days_open: int = 0
    previous_conclusion_kind: Optional[str] = None
    previous_conclusion: Optional[str] = None
    previous_next_step: Optional[str] = None
    revisit_date: Optional[str] = None
    revisit_overdue: bool = False
    echoes: list = field(default_factory=list)
    stance: str = "neutral"
    used_seeded: bool = False


def choose_stance(times_raised: int, direct_opt_in: bool = False) -> str:
    if times_raised <= 1:
        return "neutral"
    if times_raised == 2:
        return "name_the_loop"
    return "direct" if direct_opt_in else "ask_permission_to_be_direct"


def _days_between(earlier_iso: str, today: date) -> int:
    return max(0, (today - date.fromisoformat(earlier_iso)).days)


def compute_facts(current: DecisionRecord, echo_matches: list, today: date,
                  direct_opt_in: bool = False) -> Facts:
    times = max(1, len(current.mentions))
    facts = Facts(
        times_raised=times,
        first_seen=current.created_at,
        days_open=_days_between(current.created_at, today),
        stance=choose_stance(times, direct_opt_in),
        used_seeded=current.seeded,
    )
    if times > 1 and current.conclusion_kind:
        facts.previous_conclusion_kind = current.conclusion_kind
        facts.previous_conclusion = current.conclusion
        facts.previous_next_step = current.next_step
        facts.revisit_date = current.revisit_date
        if current.revisit_date:
            facts.revisit_overdue = date.fromisoformat(current.revisit_date) <= today
    for m in echo_matches:
        old = m.record
        facts.echoes.append(Echo(
            title=old.title, worries=list(old.worries),
            conclusion_kind=old.conclusion_kind, conclusion=old.conclusion,
            next_step=old.next_step, outcome_note=old.outcome_note,
            days_ago=_days_between(old.created_at, today),
            similarity=round(m.score, 2), seeded=old.seeded))
        facts.used_seeded = facts.used_seeded or old.seeded
    return facts


_STANCE_TEXT = {
    "neutral": "Ask open questions. Do not mention memory unless an echo is listed.",
    "name_the_loop": ("Say plainly, once and without judgment, that this decision has "
                      "come up before, then ask what is keeping it open."),
    "ask_permission_to_be_direct": (
        "Name the loop, then ask the user whether they want you to be more direct "
        "when a decision keeps coming back. Do not be more direct until they say yes."),
    "direct": ("The user has agreed to directness. Ask sharper, more pointed questions "
               "about what is keeping this open. Still no advice and no plans."),
}

_KIND_TEXT = {"decided": "decided", "need_more_info": "concluded they needed more information",
              "parked": "parked it"}


def render_for_prompt(facts: Facts) -> str:
    """Empty string when there is nothing to remember (first time, no echoes)."""
    if facts.times_raised <= 1 and not facts.echoes:
        return ""
    lines = ["MEMORY FACTS (counted by code. Use only these. Do not add, round or infer):"]
    if facts.times_raised > 1:
        lines.append(f"- This decision has been raised {facts.times_raised} times. "
                     f"First raised {facts.first_seen} ({facts.days_open} days ago).")
        if facts.previous_conclusion_kind:
            kind = _KIND_TEXT.get(facts.previous_conclusion_kind, facts.previous_conclusion_kind)
            line = f"- Last time the user {kind}"
            if facts.previous_conclusion:
                line += f": \"{facts.previous_conclusion}\""
            lines.append(line + ".")
            if facts.previous_next_step:
                lines.append(f"- The next step the user wrote: \"{facts.previous_next_step}\".")
            if facts.revisit_date:
                state = "has passed" if facts.revisit_overdue else "is still ahead"
                lines.append(f"- Their revisit date ({facts.revisit_date}) {state}.")
    for e in facts.echoes:
        lines.append(f"- A different, earlier decision (\"{e.title}\", {e.days_ago} days ago) "
                     f"had a similar worry.")
        if e.worries:
            lines.append("  Worries the user named then: " + "; ".join(f'"{w}"' for w in e.worries) + ".")
        if e.conclusion_kind:
            kind = _KIND_TEXT.get(e.conclusion_kind, e.conclusion_kind)
            text = f"  They {kind}"
            if e.conclusion:
                text += f": \"{e.conclusion}\""
            lines.append(text + ".")
        if e.outcome_note:
            lines.append(f"  What happened afterwards, in their words: \"{e.outcome_note}\".")
    lines.append(f"STANCE: {_STANCE_TEXT[facts.stance]}")
    lines.append("RULES FOR USING THESE FACTS: phrase them in plain, neutral words and ask "
                 "whether the pattern still fits. Never describe the user's character or "
                 "label them (no \"you are indecisive\"). Never imply failure. "
                 "\"Need more information\" and \"parked\" are valid outcomes. "
                 "No advice, no plans, no task lists.")
    return "\n".join(lines)
