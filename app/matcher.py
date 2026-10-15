"""Matches a new decision against a user's history. Two different jobs:

  SAME decision (a loop):  topic similarity high  -> "this has come back"
  ECHO (a pattern):        topic differs, worry similarity high
                           -> "last time you were worried about X..."

embed_fn(list[str]) -> list[list[float]]   (your llm.embed fits this shape)
judge_same(new, old) -> bool               (optional LLM tiebreak for the grey zone)

THE THRESHOLDS ARE STARTING GUESSES. They depend on the embedding model.
Tune them with eval/run_match_eval.py before trusting them.
"""
from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Callable, Optional

from .ledger import DecisionRecord, topic_text, worry_text


def cosine(a, b) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


@dataclass
class Match:
    record: DecisionRecord
    kind: str            # "same" | "echo"
    score: float         # similarity that triggered the match
    topic_score: float
    worry_score: float


class Matcher:
    def __init__(self, embed_fn: Callable, judge_same: Optional[Callable] = None,
                 same_high: float = 0.85, same_low: float = 0.70,
                 echo_min: float = 0.60, max_echoes: int = 2,
                 echo_needs_conclusion: bool = True) -> None:
        self.embed_fn = embed_fn
        self.judge_same = judge_same
        self.same_high = same_high
        self.same_low = same_low
        self.echo_min = echo_min
        self.max_echoes = max_echoes
        self.echo_needs_conclusion = echo_needs_conclusion

    def embed_record(self, rec: DecisionRecord) -> DecisionRecord:
        """Fill both embeddings in one call (skips if already present)."""
        if rec.topic_embedding is None or rec.worry_embedding is None:
            topic_vec, worry_vec = self.embed_fn([topic_text(rec), worry_text(rec)])
            rec.topic_embedding, rec.worry_embedding = list(topic_vec), list(worry_vec)
        return rec

    def classify(self, new: DecisionRecord, old: DecisionRecord):
        """Returns (label, topic_score, worry_score); label is same | echo | none."""
        topic = cosine(new.topic_embedding, old.topic_embedding)
        worry = cosine(new.worry_embedding, old.worry_embedding)
        if topic >= self.same_high:
            return "same", topic, worry
        if topic >= self.same_low and self.judge_same and self.judge_same(new, old):
            return "same", topic, worry
        if worry >= self.echo_min:
            return "echo", topic, worry
        return "none", topic, worry

    def find_same(self, new: DecisionRecord, history: list) -> Optional[Match]:
        best = None
        for old in history:
            if old.id == new.id:
                continue
            label, t, w = self.classify(new, old)
            if label == "same" and (best is None or t > best.topic_score):
                best = Match(old, "same", t, t, w)
        return best

    def find_echoes(self, new: DecisionRecord, history: list,
                    exclude_ids=()) -> list:
        found = []
        for old in history:
            if old.id == new.id or old.id in exclude_ids:
                continue
            if self.echo_needs_conclusion and not old.conclusion_kind:
                continue   # nothing to echo yet
            label, t, w = self.classify(new, old)
            if label == "echo":
                found.append(Match(old, "echo", w, t, w))
        found.sort(key=lambda m: m.score, reverse=True)
        return found[: self.max_echoes]


# --- Dev/test only ---------------------------------------------------------
_STOP = {"the", "a", "an", "of", "to", "and", "or", "i", "my", "me", "is", "it",
         "in", "on", "for", "that", "this", "be", "do", "should", "now", "with"}


def fake_embed(texts: list, dim: int = 256) -> list:
    """Hashed bag-of-words vectors. Measures word overlap, NOT meaning.
    Only for tests and offline demos. Never use it for the real eval."""
    out = []
    for t in texts:
        vec = [0.0] * dim
        for w in re.findall(r"[a-z]+", t.lower()):
            if w in _STOP:
                continue
            h = int(hashlib.md5(w.encode()).hexdigest(), 16)
            vec[h % dim] += 1.0
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        out.append([x / norm for x in vec])
    return out
