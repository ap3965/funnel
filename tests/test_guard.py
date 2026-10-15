from app.guard import check

GOOD = [
    "What is it about the pricing page that feels heavier than everything else on the list?",
    "Does the dread make it hard to start, or impossible to focus on anything else until you know?",
    "You said 'afraid of choosing wrong' twice, but also that either path would work. What would wrong look like?",
    "Why do you think you should rewrite it? What changed since you last felt sure?",
    "If you decided today and were wrong, what would it cost you?",
    "You described the freelance gig as money and the product as meaning. Which of those is louder right now?",
    "What would you need to know to feel ready to decide?",
]

BAD_HARD = {
    "1. Draft the headline\n2. Email the investor": "list",
    "- Talk to five customers\n- Write down your pricing": "list",
    "You should rewrite the backend after launch.": "advice",
    "I recommend a smaller version first.": "advice",
    "My advice is to wait until after launch.": "advice",
    "It's better to ship first.": "advice",
    "The best option is the smaller version.": "advice",
    "Try a one-week trial with a contractor.": "command",
    "Consider writing down what would change your mind.": "command",
    "Here's a plan for this week.": "plan",
    "Your next steps are clear now.": "plan",
    "Is there anything else?": "closure",
    "Anything else you'd like to add?": "closure",
    "": "empty",
    "What worries you? What would you lose? What would you gain? What would change?": "too many questions",
}


def test_good_replies_pass():
    for text in GOOD:
        v = check(text)
        assert v.ok, (text, v)


def test_bad_replies_are_rejected_for_the_right_reason():
    for text, reason in BAD_HARD.items():
        v = check(text)
        assert not v.ok, text
        assert any(reason in h for h in v.hard), (text, v.hard)


def test_anything_else_inside_a_real_question_is_allowed():
    # This was the failing case from the first scaffold.
    v = check("Does the dread make it hard to start, or impossible to focus on anything else until you know?")
    assert v.ok


def test_question_may_quote_advice_words():
    assert check("Why do you think you should just ship it?").ok


def test_declared_question_needs_a_question_mark():
    assert not check("That sounds hard.", kind="question").ok
    assert check("That sounds hard.", kind="observation").ok


def test_soft_flags_do_not_reject():
    v = check("Have you considered a smaller version?")
    assert v.ok and any("leading" in s for s in v.soft)
    v = check("What scares you most? And what would you do if it went well?")
    assert v.ok and any("two questions" in s for s in v.soft)


def test_long_reply_is_soft_then_hard():
    sixty_five = " ".join(["word"] * 65) + "?"
    assert check(sixty_five).ok and check(sixty_five).soft
    one_thirty = " ".join(["word"] * 130) + "?"
    assert not check(one_thirty).ok


def test_verdict_lists_each_reason_once():
    v = check("You should do it. You should do it.")
    assert v.hard.count("advice: 'you should'") == 1


# The 16-case table from the first scaffold: every case must still behave the same.
ORIGINAL_CASES = [
    ("What makes this feel urgent right now?", True),
    ("When you imagine having decided, what's the first feeling that comes up?", True),
    ("Does the dread make it hard to start, or impossible to focus on anything else until you know?", True),
    ("What would it mean for you if this took another month?", True),
    ("You mentioned fear of choosing wrong \u2014 how long has that been sitting with you?", True),
    ("Is there a part of this decision you're avoiding thinking about?", True),
    ("What would someone you trust ask you right now?", True),
    ("When you say 'it's complicated', what's the most complicated part?", True),
    ("You should try the smaller version first.", False),
    ("Here's what I recommend: 1. Pause the rewrite 2. Ship a patch 3. Reassess.", False),
    ("Consider breaking it into two phases.", False),
    ("I suggest you talk to your team before deciding.", False),
    ("The best option is to keep shipping and refactor later.", False),
    ("In conclusion, you've made up your mind \u2014 go with the rewrite.", False),
    ("Why not try a smaller experiment to reduce risk?", False),
    ("Would you rather stay safe or take the leap?", True),
]


def test_original_table_still_holds():
    for text, should_pass in ORIGINAL_CASES:
        assert check(text).ok is should_pass, text


def test_why_not_yet_is_a_fine_question():
    assert check("Why not yet? What is holding the decision back?").ok
