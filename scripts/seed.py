"""Seed demo history so session 2 can be shown. Every record is flagged seeded=True,
and the UI labels it "seeded demo". Never present it as real tester data.

  python -m scripts.seed --fake-embed                          # offline smoke test (memory only)
  python -m scripts.seed                                       # real embeddings, in-memory (lost on exit)
  USE_FIRESTORE=1 GOOGLE_CLOUD_PROJECT=<id> python -m scripts.seed   # the real demo data

Then open the app with  ?user=demo-ravi  to load it.
"""
from __future__ import annotations

import argparse

from app import config
from app.ledger import DecisionRecord, Mention
from app.ledger_store import FirestoreLedger, InMemoryLedger
from app.matcher import Matcher, fake_embed


def demo_records(user_id: str) -> list:
    backend = DecisionRecord(
        user_id=user_id, seeded=True, id="seed-001", created_at="2026-09-01",
        title="Rewrite the backend in Go or keep shipping on the Python monolith",
        options=["rewrite in Go", "keep shipping on Python"],
        worries=["choosing wrong", "3-month rewrite", "no Go experience", "losing momentum"],
        mentions=[Mention("seed-a", "2026-09-01")],
        conclusion_kind="decided",
        conclusion="Keep shipping for 6 weeks, then reassess with real usage data.",
        next_step="Ship the next two features without touching the architecture.",
        revisit_date="2026-10-15")
    pivot = DecisionRecord(
        user_id=user_id, seeded=True, id="seed-002", created_at="2026-09-20",
        title="Pivot to B2B or stay consumer",
        options=["pivot to B2B", "stay consumer", "run a 2-week B2B experiment"],
        worries=["being deluded", "8 months no revenue", "disagreement with co-founder"],
        mentions=[Mention("seed-b", "2026-09-20")],
        conclusion_kind="decided",
        conclusion="Run a 2-week B2B pilot before deciding anything.",
        next_step="Book 5 discovery calls with potential B2B customers this week.",
        revisit_date="2026-10-04")
    contractor = DecisionRecord(
        user_id=user_id, seeded=True, id="seed-003", created_at="2026-09-10",
        title="Hire a contractor or keep doing everything myself",
        options=["hire a contractor", "do it all myself"],
        worries=["afraid of choosing the wrong person", "afraid of choosing wrong"],
        mentions=[Mention("seed-c", "2026-09-10")],
        conclusion_kind="decided", conclusion="try a smaller version first",
        next_step="email two contractors about a one-week paid trial",
        outcome_note="the trial week went fine and I hired for 10 hours a week")
    return [backend, pivot, contractor]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--user", default="demo-ravi")
    ap.add_argument("--fake-embed", action="store_true", help="smoke test only; not for the real demo")
    args = ap.parse_args()

    if args.fake_embed:
        embed = fake_embed
    else:
        from app.llm import get_llm
        embed = get_llm().embed
    ledger = FirestoreLedger(project=config.GCP_PROJECT) if config.USE_FIRESTORE else InMemoryLedger()
    matcher = Matcher(embed)
    for rec in demo_records(args.user):
        matcher.embed_record(rec)
        ledger.save(rec)                       # same id again = overwrite, so re-running is safe
        print("seeded:", rec.title)
    print(f"done: {len(ledger.list_for_user(args.user))} records for '{args.user}' "
          f"({'Firestore' if config.USE_FIRESTORE else 'in-memory: lost when this script exits'})")


if __name__ == "__main__":
    main()
