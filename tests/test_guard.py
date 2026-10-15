"""
tests/test_guard.py — pytest table of ~15 good/bad strings.

Run: pytest tests/test_guard.py -v
"""

import pytest
from app.guard import check, MUST_PASS_EXAMPLES

# (text, should_pass)
CASES: list[tuple[str, bool]] = [
    # --- MUST PASS (question-only, no advice) ---
    ("What makes this feel urgent right now?", True),
    ("When you imagine having decided, what's the first feeling that comes up?", True),
    ("Does the dread make it hard to start, or impossible to focus on anything else until you know?", True),  # MUST-PASS from spec
    ("What would it mean for you if this took another month?", True),
    ("You mentioned fear of choosing wrong — how long has that been sitting with you?", True),
    ("Is there a part of this decision you're avoiding thinking about?", True),
    ("What would someone you trust ask you right now?", True),
    ("When you say 'it's complicated', what's the most complicated part?", True),
    # --- MUST FAIL (advice / plan / list) ---
    ("You should try the smaller version first.", False),
    ("Here's what I recommend: 1. Pause the rewrite 2. Ship a patch 3. Reassess.", False),
    ("Consider breaking it into two phases.", False),
    ("I suggest you talk to your team before deciding.", False),
    ("The best option is to keep shipping and refactor later.", False),
    ("In conclusion, you've made up your mind — go with the rewrite.", False),
    ("Why not try a smaller experiment to reduce risk?", False),
    # --- Soft flags (should still pass hard check) ---
    ("Would you rather stay safe or take the leap?", True),  # soft flag, not hard reject
]


@pytest.mark.parametrize("text,should_pass", CASES)
def test_guard(text: str, should_pass: bool):
    clean, reason = check(text)
    if should_pass:
        assert clean, f"Expected PASS but got REJECT (reason={reason!r}) for: {text!r}"
    else:
        assert not clean, f"Expected REJECT but got PASS for: {text!r}"


def test_must_pass_examples():
    """All strings listed in MUST_PASS_EXAMPLES in guard.py must pass."""
    for text in MUST_PASS_EXAMPLES:
        clean, reason = check(text)
        assert clean, f"MUST_PASS example rejected (reason={reason!r}): {text!r}"
