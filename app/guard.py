"""
guard.py — deterministic check that the AI only asks questions, never advises.

Hard reject patterns → retry once with stricter instruction → fall back to safe question.
Soft flag patterns → log only.

KNOWN SAFE STRINGS (must-pass, from Section 8 of spec):
  "Does the dread make it hard to start, or impossible to focus on
   anything else until you know?"
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
_log_path = Path("eval/rejections.log")
_log_path.parent.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger("funnel.guard")
_file_handler = logging.FileHandler(_log_path)
_file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
logger.addHandler(_file_handler)
logger.setLevel(logging.DEBUG)

# ---------------------------------------------------------------------------
# Hard reject patterns (any match → reject)
# ---------------------------------------------------------------------------
_HARD_REJECT: list[re.Pattern] = [
    # Numbered / bulleted lists
    re.compile(r"^\s*(\d+[\.\)]\s|\*\s|-\s)", re.MULTILINE),
    # Imperative advice verbs (whole word, case-insensitive)
    re.compile(r"\b(you should|try to|consider|i recommend|i suggest"
               r"|you could|one option is|a good idea would be"
               r"|why not|go ahead and|make sure you)\b", re.IGNORECASE),
    # Closure / resolution phrasing — NARROW: do NOT match "anything else"
    # Bad pattern from earlier draft that broke the must-pass case:
    #   re.compile(r"anything else")  <-- removed
    re.compile(
        r"\b(in conclusion|in summary|so the answer is|the best (choice|option|path|move) is"
        r"|you('ve| have) decided|i('d| would) (recommend|advise|suggest)"
        r"|sounds like you('ve| have) made up your mind)\b",
        re.IGNORECASE,
    ),
]

# ---------------------------------------------------------------------------
# Soft flag patterns (log but do not reject)
# ---------------------------------------------------------------------------
_SOFT_FLAG: list[re.Pattern] = [
    # Forced-choice framing
    re.compile(r"\bwould you (rather|prefer)\b", re.IGNORECASE),
    # Leading questions
    re.compile(r"\bisn't it (true|clear|obvious)\b", re.IGNORECASE),
]

# Safe fallback question returned when retry also fails
SAFE_FALLBACK = "What feels most unresolved about this for you right now?"

# Must-pass strings used in tests (kept here for reference)
MUST_PASS_EXAMPLES = [
    "Does the dread make it hard to start, or impossible to focus on anything else until you know?",
]


def check(text: str) -> tuple[bool, str | None]:
    """
    Returns (is_clean, reason_or_None).
    is_clean=True means the text passed all hard-reject rules.
    """
    for pattern in _HARD_REJECT:
        if pattern.search(text):
            reason = f"hard_reject pattern={pattern.pattern!r}"
            logger.warning("REJECT | %s | text=%r", reason, text[:120])
            return False, reason

    for pattern in _SOFT_FLAG:
        if pattern.search(text):
            logger.info("SOFT_FLAG | pattern=%r | text=%r", pattern.pattern, text[:120])

    return True, None


def guard_or_fallback(
    text: str,
    retry_fn: "Callable[[], str] | None" = None,
) -> str:
    """
    If text passes → return it.
    If not → call retry_fn once (if provided) with a stricter system instruction.
    If retry also fails → return SAFE_FALLBACK.
    Logs all rejections.
    """
    clean, reason = check(text)
    if clean:
        return text

    logger.warning("FIRST_REJECT | reason=%s", reason)

    if retry_fn:
        retry_text = retry_fn()
        clean2, reason2 = check(retry_text)
        if clean2:
            logger.info("RETRY_OK | text=%r", retry_text[:120])
            return retry_text
        logger.warning("RETRY_REJECT | reason=%s | falling back", reason2)

    logger.warning("FALLBACK_USED")
    return SAFE_FALLBACK
