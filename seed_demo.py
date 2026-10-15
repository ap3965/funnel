"""
seed_demo.py — seeds 2 past decisions into the store so session 2 can be demoed.
Run: python seed_demo.py

CLEARLY LABELED as seeded demo data (seeded=True field added at runtime via store metadata).
"""

from __future__ import annotations

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from app.schemas import Decision, Commit
from app.store import get_store

SEEDED: list[dict] = [
    {
        "id": "seed-001",
        "created_at": "2026-09-01T10:00:00+00:00",
        "dump": "Should I rewrite the backend in Go or keep shipping on the Python monolith? "
                "The monolith is slow but I know it. Go would be faster but it's a 3-month rewrite.",
        "worries": ["choosing wrong", "3-month rewrite", "no Go experience", "losing momentum"],
        "options": ["rewrite in Go", "keep shipping on Python"],
        "conclusion": "Keep shipping for 6 weeks, then reassess with real usage data.",
        "next_step": "Ship the next two features without touching the architecture.",
        "revisit_date": "2026-10-15",
    },
    {
        "id": "seed-002",
        "created_at": "2026-09-20T14:30:00+00:00",
        "dump": "My co-founder wants to pivot to B2B. I built this for consumers and it still feels right. "
                "But 8 months in with zero revenue makes me doubt myself.",
        "worries": ["being deluded", "8 months no revenue", "disagreement with co-founder"],
        "options": ["pivot to B2B", "stay consumer", "run a 2-week B2B experiment"],
        "conclusion": "Run a 2-week B2B pilot before deciding anything.",
        "next_step": "Book 5 discovery calls with potential B2B customers this week.",
        "revisit_date": "2026-10-04",
    },
]


def seed():
    store = get_store()
    for data in SEEDED:
        existing = store.get_decision(data["id"])
        if existing:
            print(f"  Already exists: {data['id']}")
            continue
        d = Decision(**{k: v for k, v in data.items() if k != "revisit_date"},
                     revisit_date=data.get("revisit_date"))
        store.save_decision(d)
        print(f"  Seeded: {data['id']} — {data['dump'][:60]}…")


if __name__ == "__main__":
    print("[seed_demo.py] Seeding demo history (CLEARLY LABELED as seeded)…")
    seed()
    print("Done. Start the server and open / to see the ledger.")
