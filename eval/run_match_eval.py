"""Measures matcher accuracy on hand-labelled decision pairs, and shows where to
set the thresholds.

  python -m eval.run_match_eval                    # real embeddings (app.llm.embed)
  python -m eval.run_match_eval --fake-embed       # word-overlap vectors, only to check the script runs

Labels:  same = the same decision, reworded   echo = different decision, similar worry
         none = unrelated

Read the "separation" section first. If the lowest score of a positive class is
below the highest score of the negative class, no threshold can fix it: the
embeddings (or the text we embed) are the problem, not the threshold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.ledger import DecisionRecord
from app.matcher import Matcher, fake_embed

PAIRS = Path(__file__).with_name("match_pairs.json")


def _real_embed(texts):
    from app.llm import get_llm
    return get_llm().embed(texts)


def _rec(d: dict, matcher: Matcher) -> DecisionRecord:
    rec = DecisionRecord(user_id="eval", title=d["title"],
                         options=d["options"], worries=d["worries"])
    return matcher.embed_record(rec)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fake-embed", action="store_true")
    ap.add_argument("--same-high", type=float, default=0.85)
    ap.add_argument("--same-low", type=float, default=0.70)
    ap.add_argument("--echo-min", type=float, default=0.60)
    args = ap.parse_args()

    matcher = Matcher(fake_embed if args.fake_embed else _real_embed,
                      same_high=args.same_high, same_low=args.same_low,
                      echo_min=args.echo_min)
    pairs = json.loads(PAIRS.read_text())

    rows, correct, grey = [], 0, 0
    for p in pairs:
        a, b = _rec(p["a"], matcher), _rec(p["b"], matcher)
        got, topic, worry = matcher.classify(b, a)
        if p["label"] == "same" and args.same_low <= topic < args.same_high:
            grey += 1               # would need the LLM tiebreak
        ok = got == p["label"]
        correct += ok
        rows.append((p["label"], got, topic, worry, p["a"]["title"][:38], p["b"]["title"][:38], ok))

    print(f"{'want':5} {'got':5} {'topic':>6} {'worry':>6}  pair")
    for want, got, t, w, a, b, ok in rows:
        print(f"{want:5} {got:5} {t:6.2f} {w:6.2f}  {'' if ok else '<< MISS  '}{a} | {b}")

    n = len(rows)
    print(f"\naccuracy: {correct}/{n} = {correct / n:.0%}   "
          f"(thresholds: same>={args.same_high}, grey>={args.same_low}, echo>={args.echo_min})")
    print(f"'same' pairs that landed in the grey zone (need the LLM tiebreak): {grey}")

    def scores(label, idx):
        return [r[idx] for r in rows if r[0] == label]

    same_t, other_t = scores("same", 2), scores("echo", 2) + scores("none", 2)
    echo_w, none_w = scores("echo", 3), scores("none", 3)
    print("\nseparation (positive class must stay ABOVE the negative class):")
    print(f"  topic: lowest 'same' = {min(same_t):.2f}   highest non-'same' = {max(other_t):.2f}")
    print(f"  worry: lowest 'echo' = {min(echo_w):.2f}   highest 'none'     = {max(none_w):.2f}")


if __name__ == "__main__":
    main()
