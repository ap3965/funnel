"""
store.py — abstract interface + two backends.

STORE_BACKEND env var: "memory" (default) | "firestore"
"""

from __future__ import annotations

import os
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.schemas import Commit, Decision


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------
class DecisionStore(ABC):
    @abstractmethod
    def save_decision(self, decision: Decision) -> Decision: ...

    @abstractmethod
    def get_decision(self, decision_id: str) -> Decision | None: ...

    @abstractmethod
    def list_decisions(self) -> list[Decision]: ...

    @abstractmethod
    def update_commit(self, decision_id: str, commit: Commit) -> Decision | None: ...

    def new_id(self) -> str:
        return str(uuid.uuid4())

    def now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# In-memory backend (dev + fallback)
# ---------------------------------------------------------------------------
class MemoryStore(DecisionStore):
    def __init__(self) -> None:
        self._data: dict[str, Decision] = {}

    def save_decision(self, decision: Decision) -> Decision:
        self._data[decision.id] = decision
        return decision

    def get_decision(self, decision_id: str) -> Decision | None:
        return self._data.get(decision_id)

    def list_decisions(self) -> list[Decision]:
        return sorted(self._data.values(), key=lambda d: d.created_at, reverse=True)

    def update_commit(self, decision_id: str, commit: Commit) -> Decision | None:
        d = self._data.get(decision_id)
        if not d:
            return None
        d.conclusion = commit.conclusion
        d.next_step = commit.next_step
        d.revisit_date = commit.revisit_date
        self._data[decision_id] = d
        return d


# ---------------------------------------------------------------------------
# Firestore backend (production)
# ---------------------------------------------------------------------------
class FirestoreStore(DecisionStore):
    COLLECTION = "decisions"

    def __init__(self) -> None:
        from google.cloud import firestore  # type: ignore
        self._db = firestore.Client()

    def _doc_ref(self, decision_id: str):
        return self._db.collection(self.COLLECTION).document(decision_id)

    def save_decision(self, decision: Decision) -> Decision:
        self._doc_ref(decision.id).set(decision.model_dump(mode="json"))
        return decision

    def get_decision(self, decision_id: str) -> Decision | None:
        snap = self._doc_ref(decision_id).get()
        if not snap.exists:
            return None
        return Decision(**snap.to_dict())

    def list_decisions(self) -> list[Decision]:
        docs = self._db.collection(self.COLLECTION).order_by(
            "created_at", direction="DESCENDING"
        ).stream()
        return [Decision(**d.to_dict()) for d in docs]

    def update_commit(self, decision_id: str, commit: Commit) -> Decision | None:
        ref = self._doc_ref(decision_id)
        snap = ref.get()
        if not snap.exists:
            return None
        ref.update({
            "conclusion": commit.conclusion,
            "next_step": commit.next_step,
            "revisit_date": commit.revisit_date.isoformat() if commit.revisit_date else None,
        })
        return self.get_decision(decision_id)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------
_store: DecisionStore | None = None


def get_store() -> DecisionStore:
    global _store
    if _store is None:
        backend = os.getenv("STORE_BACKEND", "memory").lower()
        if backend == "firestore":
            _store = FirestoreStore()
        else:
            _store = MemoryStore()
    return _store
