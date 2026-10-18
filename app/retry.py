"""Retry + fallback for model calls. Dependency-free so it can be tested offline.

Google's API sometimes answers 503 ("high demand") or 429 for a few seconds. Those are
worth a short wait and another try. Anything else (bad key, bad request, model not found)
is not: move straight to the next model.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

TRANSIENT = (429, 500, 502, 503, 504)


def run_with_fallback(call: Callable, models: list, attempts: int = 3,
                      delays: tuple = (1.0, 2.0), sleep: Callable = time.sleep,
                      on_error: Optional[Callable] = None):
    """call(model) -> result. Tries each model up to `attempts` times on transient errors."""
    errors = []
    for model in models:
        for attempt in range(1, attempts + 1):
            try:
                return call(model)
            except Exception as exc:
                errors.append(exc)
                if on_error:
                    on_error(model, attempt, exc)
                if getattr(exc, "code", None) in TRANSIENT and attempt < attempts:
                    sleep(delays[min(attempt - 1, len(delays) - 1)])
                    continue
                break                                   # not worth retrying: next model
    # Report the most useful failure: a 404 from the fallback model should not hide a 503/429.
    raise next((e for e in errors if getattr(e, "code", None) != 404), errors[-1])
