"""Runs every dump in eval/dumps.json through the REAL pipeline (extract -> memory -> question -> guard).
Needs GEMINI_API_KEY. Prints each first question so YOU can judge quality, and the guard numbers for the deck.

  python -m eval.run_eval
"""
from __future__ import annotations

import json
from pathlib import Path

from app.ledger_store import InMemoryLedger
from app.llm import get_llm
from app.matcher import Matcher
from app.memory import MemoryService
from app.session import SessionManager

DUMPS = Path(__file__).with_name("dumps.json")


def main() -> None:
    llm = get_llm()
    mgr = SessionManager(llm, MemoryService(InMemoryLedger(), Matcher(llm.embed)))
    rows = []
    for item in json.loads(DUMPS.read_text()):
        out = mgr.start(f"eval-{item['id']}", item["dump"])
        t = out["turn"]
        rows.append({"id": item["id"], "type": t["type"], "words": len(t["text"].split()), "text": t["text"]})
        print(f"\n[{item['id']}] {item.get('note', '')}\n  ({t['type']}, {len(t['text'].split())} words) {t['text']}")
    s = mgr.stats
    checked, rejected = s["guard_checked"], s["guard_rejected"]
    print("\n" + "=" * 60)
    print(f"dumps: {len(rows)}   replies checked by the guard: {checked}")
    print(f"rejected on first sight: {rejected} ({rejected / max(checked, 1):.0%})   "
          f"fell back to a generic question: {s['guard_fallbacks']}   soft flags: {s['guard_soft']}")
    print("Deck line:  \"the guard blocked %d of %d model replies before the user saw them\"" % (rejected, checked))
    print("Now READ the questions above. Are they specific to each dump, or could they be asked of anyone?")
    Path(__file__).with_name("last_run.json").write_text(json.dumps({"stats": s, "rows": rows}, indent=2))


if __name__ == "__main__":
    main()
