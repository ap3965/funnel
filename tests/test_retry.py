import pytest

from app.retry import run_with_fallback


class Boom(Exception):
    def __init__(self, code):
        super().__init__(f"error {code}")
        self.code = code


def _call(script):
    """script: list of results/exceptions consumed in order; records which model was used."""
    seen = []

    def call(model):
        seen.append(model)
        item = script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item
    return call, seen


def test_busy_then_success_retries_the_same_model_quietly():
    call, seen = _call([Boom(503), Boom(503), "ok"])
    slept = []
    assert run_with_fallback(call, ["a", "b"], sleep=slept.append) == "ok"
    assert seen == ["a", "a", "a"] and slept == [1.0, 2.0]


def test_still_busy_after_retries_moves_to_the_fallback_model():
    call, seen = _call([Boom(503), Boom(503), Boom(503), "ok"])
    assert run_with_fallback(call, ["a", "b"], sleep=lambda s: None) == "ok"
    assert seen == ["a", "a", "a", "b"]


def test_non_transient_errors_are_not_retried():
    call, seen = _call([Boom(400), "ok"])
    slept = []
    assert run_with_fallback(call, ["a", "b"], sleep=slept.append) == "ok"
    assert seen == ["a", "b"] and slept == []


def test_all_models_failing_raises_the_most_useful_error():
    call, _ = _call([Boom(503)] * 3 + [Boom(404)])
    with pytest.raises(Boom) as info:
        run_with_fallback(call, ["a", "b"], sleep=lambda s: None)
    assert info.value.code == 503            # not the 404 from the fallback model


def test_errors_without_a_code_go_straight_to_the_next_model():
    call, seen = _call([ValueError("bad json"), "ok"])
    assert run_with_fallback(call, ["a", "b"], sleep=lambda s: None) == "ok"
    assert seen == ["a", "b"]


def test_on_error_is_told_about_every_failure():
    call, _ = _call([Boom(503), "ok"])
    events = []
    run_with_fallback(call, ["a"], sleep=lambda s: None, on_error=lambda m, a, e: events.append((m, a, e.code)))
    assert events == [("a", 1, 503)]
