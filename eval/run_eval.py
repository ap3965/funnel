"""Runs the sample dumps in eval/dumps.json through the REAL pipeline (extract -> memory -> question -> guard).
Needs GEMINI_API_KEY. Prints every first reply so YOU can judge quality, plus the guard numbers for the deck.

  python -m eval.run_eval                       # all dumps, 10 s pause between them
  python -m eval.run_eval --start 9             # resume from dump 9 (1-based) after a rate limit
  python -m eval.run_eval --sleep 20            # slower, safer on the free tier

It never crashes on a rate limit: it waits and retries once, records any failure, and always prints a summary.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

DUMPS = Path(__file__).with_name("dumps.json")


def run(mgr, items, sleep_s: float = 10.0, sleep_fn=time.sleep, retry_wait: float = 65.0) -> tuple:
    rows, failures = [], []
    for n, item in enumerate(items):
        if n and sleep_s:
            sleep_fn(sleep_s)                          # spread calls out: free tiers limit requests per minute
        out = None
        for attempt in (1, 2):
            try:
                out = mgr.start(f"eval-{item['id']}", item["dump"])
                break
            except Exception as exc:
                code = getattr(exc, "code", None)
                if attempt == 1 and code in (429, 500, 503, 504):
                    print(f"  ... {item['id']}: rate limited or busy ({code}); waiting {retry_wait:.0f}s, then one retry", flush=True)
                    sleep_fn(retry_wait)
                    continue
                failures.append({"id": item["id"], "error": type(exc).__name__, "code": code})
                print(f"  !! {item['id']} failed: {type(exc).__name__} (code {code})", flush=True)
                break
        if out:
            t = out["turn"]
            rows.append({"id": item["id"], "type": t["type"], "words": len(t["text"].split()), "text": t["text"]})
            print(f"\n[{item['id']}] {item.get('note', '')}\n  ({t['type']}, {len(t['text'].split())} words) {t['text']}", flush=True)
    return rows, failures


def summary(stats: dict, rows: list, failures: list, total: int) -> str:
    checked, rejected = stats["guard_checked"], stats["guard_rejected"]
    kinds = {k: sum(1 for r in rows if r["type"] == k) for k in ("question", "observation")}
    words = [r["words"] for r in rows]
    lines = ["", "=" * 60,
             f"dumps attempted: {total}   completed: {len(rows)}   failed: {len(failures)}",
             f"replies checked by the guard: {checked}",
             f"rejected on first sight: {rejected} ({rejected / max(checked, 1):.0%})   "
             f"fell back to a generic question: {stats['guard_fallbacks']}   soft flags: {stats['guard_soft']}",
             f"reply types: {kinds['question']} questions, {kinds['observation']} observations"
             + (f"   length: {min(words)}-{max(words)} words" if words else "")]
    if failures:
        lines.append("failed dumps (re-run with --start): " + ", ".join(f["id"] for f in failures))
    lines.append(f'Deck line: "the guard blocked {rejected} of {checked} model replies before the user saw them (n={len(rows)} dumps, first replies only)"')
    lines.append("Now READ the replies above. Are they specific to each dump, or could they be asked of anyone?")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", type=int, default=1, help="first dump to run (1-based)")
    ap.add_argument("--sleep", type=float, default=10.0, help="seconds to pause between dumps")
    args = ap.parse_args()

    from app.ledger_store import InMemoryLedger
    from app.llm import get_llm
    from app.matcher import Matcher
    from app.memory import MemoryService
    from app.session import SessionManager

    llm = get_llm()
    mgr = SessionManager(llm, MemoryService(InMemoryLedger(), Matcher(llm.embed)))
    items = json.loads(DUMPS.read_text())[max(args.start, 1) - 1:]
    rows, failures = [], []
    try:
        rows, failures = run(mgr, items, sleep_s=args.sleep)
    except KeyboardInterrupt:
        print("\nstopped by you; printing what we have")
    print(summary(mgr.stats, rows, failures, len(items)))
    Path(__file__).with_name("last_run.json").write_text(json.dumps({"stats": mgr.stats, "rows": rows, "failures": failures}, indent=2))


if __name__ == "__main__":
    main()