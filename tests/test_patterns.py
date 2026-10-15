from datetime import date

from app.ledger import DecisionRecord, Mention
from app.matcher import Match
from app.patterns import choose_stance, compute_facts, render_for_prompt

TODAY = date(2026, 10, 15)


def _rec(**kw):
    base = dict(user_id="u", title="Rewrite the backend or keep shipping",
                created_at="2026-09-20")
    base.update(kw)
    return DecisionRecord(**base)


def _mentions(n):
    return [Mention(f"s{i}", "2026-09-20") for i in range(n)]


def test_stance_escalates_with_count():
    assert choose_stance(1) == "neutral"
    assert choose_stance(2) == "name_the_loop"
    assert choose_stance(3) == "ask_permission_to_be_direct"
    assert choose_stance(5) == "ask_permission_to_be_direct"


def test_direct_only_after_opt_in():
    assert choose_stance(3, direct_opt_in=True) == "direct"
    assert choose_stance(2, direct_opt_in=True) == "name_the_loop"


def test_counts_and_days_open():
    f = compute_facts(_rec(mentions=_mentions(3)), [], TODAY)
    assert f.times_raised == 3
    assert f.days_open == 25
    assert f.first_seen == "2026-09-20"


def test_revisit_overdue_flag():
    past = _rec(mentions=_mentions(2), conclusion_kind="parked",
                conclusion="wait for more data", revisit_date="2026-10-01")
    future = _rec(mentions=_mentions(2), conclusion_kind="parked",
                  conclusion="wait for more data", revisit_date="2026-11-01")
    assert compute_facts(past, [], TODAY).revisit_overdue is True
    assert compute_facts(future, [], TODAY).revisit_overdue is False


def test_first_time_no_echo_renders_nothing():
    f = compute_facts(_rec(mentions=_mentions(1)), [], TODAY)
    assert render_for_prompt(f) == ""


def test_loop_block_contains_counted_facts():
    cur = _rec(mentions=_mentions(3), conclusion_kind="parked",
               conclusion="wait for more data", revisit_date="2026-10-01")
    text = render_for_prompt(compute_facts(cur, [], TODAY))
    assert "raised 3 times" in text
    assert "25 days ago" in text
    assert "wait for more data" in text
    assert "has passed" in text
    assert "ask the user whether they want you to be more direct" in text


def test_echo_block_uses_the_users_own_words():
    old = _rec(title="Hire a contractor", created_at="2026-09-10",
               worries=["afraid of choosing wrong"], conclusion_kind="decided",
               conclusion="try a smaller version first", mentions=_mentions(1))
    m = Match(old, "echo", 0.68, 0.06, 0.68)
    text = render_for_prompt(compute_facts(_rec(mentions=_mentions(1)), [m], TODAY))
    assert "Hire a contractor" in text
    assert "afraid of choosing wrong" in text
    assert "try a smaller version first" in text
    assert "35 days ago" in text


def test_block_never_labels_the_user():
    cur = _rec(mentions=_mentions(4))
    text = render_for_prompt(compute_facts(cur, [], TODAY, direct_opt_in=True)).lower()
    # The only judgment words allowed are inside the instruction NOT to use them.
    assert "indecisive" in text            # appears only in the prohibition
    assert text.count("indecisive") == 1
    assert "you failed" not in text and "procrastinat" not in text


def test_seeded_history_is_flagged():
    old = _rec(title="Hire a contractor", worries=["afraid"], conclusion_kind="decided",
               seeded=True, mentions=_mentions(1))
    f = compute_facts(_rec(mentions=_mentions(1)), [Match(old, "echo", 0.7, 0.0, 0.7)], TODAY)
    assert f.used_seeded is True
