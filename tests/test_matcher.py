from app.ledger import DecisionRecord
from app.matcher import Matcher, cosine, fake_embed


def _embedded(matcher, title, options, worries, **kw):
    rec = DecisionRecord(user_id="u", title=title, options=options, worries=worries, **kw)
    return matcher.embed_record(rec)


def _matcher(**kw):
    return Matcher(fake_embed, **kw)


def test_cosine_basics():
    assert cosine([1, 0], [1, 0]) == 1.0
    assert cosine([1, 0], [0, 1]) == 0.0
    assert cosine([], [1]) == 0.0


def test_reworded_decision_is_the_same_decision():
    m = _matcher()
    old = _embedded(m, "Rewrite the backend or keep shipping features",
                    ["rewrite backend", "keep shipping"], ["afraid of choosing wrong"])
    new = _embedded(m, "Should I rewrite the backend now or keep shipping?",
                    ["rewrite", "keep shipping features"], ["worried about losing momentum"])
    hit = m.find_same(new, [old])
    assert hit is not None and hit.record.id == old.id


def test_different_topic_same_worry_is_an_echo_not_a_loop():
    m = _matcher()
    past = _embedded(m, "Hire a contractor or do everything myself",
                     ["hire contractor", "do it myself"],
                     ["afraid of choosing the wrong person", "afraid of choosing wrong"],
                     conclusion_kind="decided", conclusion="try a smaller version first")
    new = _embedded(m, "Rewrite the backend or keep shipping features",
                    ["rewrite backend", "keep shipping"], ["afraid of choosing wrong"])
    assert m.find_same(new, [past]) is None
    echoes = m.find_echoes(new, [past])
    assert [e.record.id for e in echoes] == [past.id]


def test_echo_needs_a_conclusion_to_echo():
    m = _matcher()
    past = _embedded(m, "Hire a contractor or do everything myself",
                     ["hire contractor"], ["afraid of choosing wrong"])   # no conclusion yet
    new = _embedded(m, "Rewrite the backend or keep shipping",
                    ["rewrite"], ["afraid of choosing wrong"])
    assert m.find_echoes(new, [past]) == []


def test_unrelated_decisions_match_nothing():
    m = _matcher()
    past = _embedded(m, "Pick a pricing model for launch",
                     ["flat pricing", "usage-based pricing"],
                     ["might scare away early customers"],
                     conclusion_kind="decided", conclusion="flat")
    new = _embedded(m, "Hire a contractor or do everything myself",
                    ["hire contractor"], ["afraid of choosing the wrong person"])
    assert m.find_same(new, [past]) is None
    assert m.find_echoes(new, [past]) == []


def test_grey_zone_uses_the_llm_tiebreak():
    m_yes = _matcher(same_high=0.99, same_low=0.5, judge_same=lambda n, o: True)
    m_no = _matcher(same_high=0.99, same_low=0.5, judge_same=lambda n, o: False)
    for matcher, expected in ((m_yes, True), (m_no, False)):
        old = _embedded(matcher, "Rewrite the backend or keep shipping features",
                        ["rewrite backend"], ["x"])
        new = _embedded(matcher, "Should I rewrite the backend now or keep shipping?",
                        ["rewrite"], ["y"])
        assert (matcher.find_same(new, [old]) is not None) is expected


def test_embed_record_is_idempotent_and_makes_one_call():
    calls = []

    def counting(texts):
        calls.append(texts)
        return fake_embed(texts)

    m = Matcher(counting)
    rec = DecisionRecord(user_id="u", title="t", worries=["w"])
    m.embed_record(rec)
    m.embed_record(rec)
    assert len(calls) == 1 and len(calls[0]) == 2


def test_max_echoes_is_respected():
    m = _matcher(max_echoes=1)
    pasts = [_embedded(m, f"Topic {i} thing{i}", [f"opt{i}"], ["afraid of choosing wrong"],
                       conclusion_kind="decided") for i in range(3)]
    new = _embedded(m, "Completely other subject", ["x"], ["afraid of choosing wrong"])
    assert len(m.find_echoes(new, pasts)) == 1
