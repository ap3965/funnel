"""Measures matcher accuracy on hand-labelled decision pairs, and shows where to
set the thresholds.

  python -m eval.run_match_eval                    # real embeddings (app.llm.embed)
  python -m eval.run_match_eval --fake-embed       # word-overlap vectors, only to check the script runs
  python -m eval.run_match_eval --sleep 8          # slower, safer on the free tier
  python -m eval.run_match_eval --same-high 0.875 --echo-min 0.86   # re-score with other thresholds

Rate limits: embeddings are cached in eval/embed_cache.json, one entry per unique text. A rerun, or a run
with different thresholds, only embeds texts it has not seen, so it usually needs no API calls at all. A rate
limit makes the script wait and retry once; if a pair still fails it is listed and left out of the score.

Labels:  same = the same decision, reworded   echo = different decision, similar worry
         none = unrelated

Read the "separation" section first. If the lowest score of a positive class is
below the highest score of the negative class, no threshold can fix it: the
embeddings (or the text we embed) are the problem, not the threshold.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from app.ledger import DecisionRecord
from app.matcher import Matcher, fake_embed

PAIRS = Path(__file__).with_name("match_pairs.json")
CACHE = Path(__file__).with_name("embed_cache.json")
RETRYABLE = (429, 500, 503, 504)


class CachedEmbed:
    """Wraps an embed function: caches by text on disk, pauses between API calls, retries once on rate limits."""

    def __init__(self, inner, path=CACHE, sleep_s=5.0, retry_wait=65.0, sleep_fn=time.sleep):
        self.inner, self.path = inner, path
        self.sleep_s, self.retry_wait, self.sleep_fn = sleep_s, retry_wait, sleep_fn
        self.api_calls = 0
        try:
            self.cache = json.loads(path.read_text()) if path and path.exists() else {}
        except (OSError, ValueError):
            self.cache = {}

    def __call__(self, texts):
        missing = [t for t in dict.fromkeys(texts) if t not in self.cache]
        if missing:
            if self.api_calls and self.sleep_s:
                self.sleep_fn(self.sleep_s)           # spread calls out: free tiers limit requests per minute
            vecs = self._call(missing)
            self.api_calls += 1
            for t, v in zip(missing, vecs):
                self.cache[t] = list(v)
            if self.path:
                self.path.write_text(json.dumps(self.cache))
        return [self.cache[t] for t in texts]

    def _call(self, texts):
        for attempt in (1, 2):
            try:
                return self.inner(texts)
            except Exception as exc:
                code = getattr(exc, "code", None)
                if attempt == 1 and code in RETRYABLE:
                    print(f"  ... rate limited or busy ({code}); waiting {self.retry_wait:.0f}s, then one retry", flush=True)
                    self.sleep_fn(self.retry_wait)
                    continue
                raise


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
    ap.add_argument("--sleep", type=float, default=5.0, help="seconds to pause between API calls")
    ap.add_argument("--no-cache", action="store_true", help="ignore and do not write eval/embed_cache.json")
    args = ap.parse_args()

    embed_fn = fake_embed if args.fake_embed else CachedEmbed(_real_embed, None if args.no_cache else CACHE, args.sleep)
    matcher = Matcher(embed_fn,
                      same_high=args.same_high, same_low=args.same_low,
                      echo_min=args.echo_min)
    pairs = json.loads(PAIRS.read_text())

    rows, correct, grey, failures = [], 0, 0, []
    for i, p in enumerate(pairs, 1):
        try:
            a, b = _rec(p["a"], matcher), _rec(p["b"], matcher)
            got, topic, worry = matcher.classify(b, a)
        except KeyboardInterrupt:
            print("\nstopped by you; scoring what we have")
            break
        except Exception as exc:
            failures.append(i)
            print(f"  !! pair {i} failed: {type(exc).__name__} (code {getattr(exc, 'code', None)})", flush=True)
            continue
        if p["label"] == "same" and args.same_low <= topic < args.same_high:
            grey += 1               # would need the LLM tiebreak
        ok = got == p["label"]
        correct += ok
        rows.append((p["label"], got, topic, worry, p["a"]["title"][:38], p["b"]["title"][:38], ok))

    print(f"{'want':5} {'got':5} {'topic':>6} {'worry':>6}  pair")
    for want, got, t, w, a, b, ok in rows:
        print(f"{want:5} {got:5} {t:6.2f} {w:6.2f}  {'' if ok else '<< MISS  '}{a} | {b}")

    n = len(rows)
    if failures:
        print(f"\n{len(failures)} pair(s) failed and are NOT in the score: {failures}. Run again: finished embeddings are cached.")
    if not n:
        print("no pairs scored")
        return
    print(f"\naccuracy: {correct}/{n} = {correct / n:.0%}   "
          f"(thresholds: same>={args.same_high}, grey>={args.same_low}, echo>={args.echo_min})")
    print(f"'same' pairs that landed in the grey zone (need the LLM tiebreak): {grey}")

    def scores(label, idx):
        return [r[idx] for r in rows if r[0] == label]

    same_t, other_t = scores("same", 2), scores("echo", 2) + scores("none", 2)
    echo_w, none_w = scores("echo", 3), scores("none", 3)
    print("\nseparation (positive class must stay ABOVE the negative class):")
    if same_t and other_t:
        print(f"  topic: lowest 'same' = {min(same_t):.2f}   highest non-'same' = {max(other_t):.2f}")
    if echo_w and none_w:
        print(f"  worry: lowest 'echo' = {min(echo_w):.2f}   highest 'none'     = {max(none_w):.2f}")


if __name__ == "__main__":
    main()