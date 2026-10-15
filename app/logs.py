"""One-line JSON logs on stdout. Cloud Run sends stdout to Cloud Logging.

PRIVACY RULE: never log what the user typed (dump, answers, conclusions).
Log only event names, counts, and the MODEL's own rejected text.
"""
from __future__ import annotations

import json
import time


def log_event(event: str, **fields) -> None:
    print(json.dumps({"event": event, "t": round(time.time(), 1), **fields}), flush=True)
