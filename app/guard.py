"""The output guard. Every AI reply passes through check() before the user sees it.

Funnel's AI may only ASK or OBSERVE. It may not advise, plan, or list tasks.
This is enforced here, in code, not just in the prompt.

Hard problems -> the reply is rejected and regenerated.
Soft problems -> the reply is allowed but logged (they are the early warning signs).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Verdict:
    ok: bool
    hard: list = field(default_factory=list)
    soft: list = field(default_factory=list)


_LIST_LINE = re.compile(r"^\s*(\d+[.)]|[-*\u2022])\s+", re.M)

# Advice phrased as a statement. Checked on non-question sentences only, so a
# question like "Why do you think you should rewrite it?" is not rejected.
_ADVICE = [
    re.compile(r"\byou (should|ought to|need to|must|have to|had better|could try|might want to|may want to)\b", re.I),
    re.compile(r"\b(i|we) (recommend|suggest|advise|propose)\b", re.I),
    re.compile(r"\b(my|the) (advice|recommendation|suggestion)\b", re.I),
    re.compile(r"\bit('s| is) (best|better|wise|smart|important) (to|that you)\b", re.I),
    re.compile(r"\b(you're|you are) better off\b", re.I),
    re.compile(r"\bthe (best|right|smart|safest) (option|choice|move|path|call)\b", re.I),
]
_COMMAND_START = re.compile(
    r"^\s*(try|consider|start|begin|make sure|remember to|focus on|take|write down|set up|"
    r"break (it|this) down|think about|decide|pick|choose|talk to|ask yourself|go with|just)\b", re.I)
# Advice disguised as a question ("Why not try...?"). Checked on ALL text, questions included.
_WHY_NOT = re.compile(
    r"\bwhy not (try|just|go|take|do|start|ship|hire|ask|talk|make|pick|choose|use|build|write|wait|consider|keep|stay|rewrite|run)\b", re.I)
# The AI declaring a verdict or closing the matter for the user (statements only).
_VERDICT = re.compile(
    r"\b(in conclusion|in summary|so the answer is|you('ve| have) (decided|made up your mind)|sounds like you('ve| have) (decided|made up your mind))\b", re.I)
_PLAN_WORDS = re.compile(
    r"\b(next steps?|action (plan|items?)|to-?do( list)?|step \d|here'?s (a|the|your|my) (plan|list|approach|suggestion))\b", re.I)
_CLOSURE = re.compile(
    r"^\s*(is there |was there )?anything else"
    r"( you('d| would) (like|want) to (add|share|say|cover|talk about))?\s*\??\s*$", re.I)
_LEADING = re.compile(
    r"\b(have you (considered|thought about|tried)|why (don'?t|not) you|what if you (just )?(tried|took|did|made|went)|"
    r"wouldn'?t it be (better|easier|smarter|wiser))\b", re.I)

MAX_WORDS_HARD = 120
MAX_WORDS_SOFT = 60


def _sentences(text: str) -> list:
    return [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s]


def check(text: Optional[str], kind: Optional[str] = None) -> Verdict:
    """kind: 'question' | 'observation' | None (skip the type-specific check)."""
    hard, soft = [], []
    text = (text or "").strip()
    if not text:
        return Verdict(False, ["empty"], [])

    if _LIST_LINE.search(text):
        hard.append("list: numbered or bulleted lines")
    if _PLAN_WORDS.search(text):
        hard.append("plan: plan or task-list wording")
    m = _WHY_NOT.search(text)
    if m:
        hard.append(f"advice: '{m.group(0).lower()}' (advice phrased as a question)")
    if _CLOSURE.match(text):
        hard.append("closure: wrap-up line, not a question about the decision")

    for sent in _sentences(text):
        if sent.endswith("?"):
            continue                                  # questions may quote advice-like words
        for pat in _ADVICE:
            m = pat.search(sent)
            if m:
                hard.append(f"advice: '{m.group(0).lower()}'")
        m = _VERDICT.search(sent)
        if m:
            hard.append(f"verdict: '{m.group(0).lower()}'")
        m = _COMMAND_START.match(sent)
        if m:
            hard.append(f"command: starts with '{m.group(1).lower()}'")

    words = len(text.split())
    if words > MAX_WORDS_HARD:
        hard.append(f"length: {words} words")
    elif words > MAX_WORDS_SOFT:
        soft.append(f"length: {words} words")

    q_marks = text.count("?")
    if q_marks > 2:
        hard.append(f"too many questions: {q_marks}")
    elif q_marks == 2:
        soft.append("two questions in one reply")
    if kind == "question" and q_marks == 0:
        hard.append("type is 'question' but there is no question mark")

    m = _LEADING.search(text)
    if m:
        soft.append(f"leading: '{m.group(0).lower()}' (may smuggle in an option)")

    # de-duplicate, keep order
    hard = list(dict.fromkeys(hard))
    return Verdict(ok=not hard, hard=hard, soft=soft)
