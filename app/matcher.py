"""
matcher.py — finds similar past decisions by WORRY similarity, not topic.
Uses embeddings + cosine similarity.
Falls back gracefully if no embeddings stored.
"""

from __future__ import annotations

import math

from app.schemas import Decision


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


def find_similar(
    current_worries: list[str],
    current_embedding: list[float] | None,
    all_decisions: list[Decision],
    top_k: int = 3,
    threshold: float = 0.75,
) -> list[Decision]:
    """
    Returns the top-k most similar past decisions by worry embedding similarity.
    Falls back to keyword overlap if embeddings are unavailable.
    """
    if not all_decisions:
        return []

    # ---- embedding path ----
    if current_embedding:
        scored = []
        for d in all_decisions:
            if d.embedding:
                score = _cosine(current_embedding, d.embedding)
                if score >= threshold:
                    scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_k]]

    # ---- keyword fallback ----
    current_kw = {w.lower() for worry in current_worries for w in worry.split() if len(w) >= 4}
    if not current_kw:
        return []
    scored = []
    for d in all_decisions:
        past_kw = {w.lower() for worry in d.worries for w in worry.split() if len(w) >= 4}
        overlap = len(current_kw & past_kw)
        if overlap > 0:
            scored.append((overlap, d))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [d for _, d in scored[:top_k]]
