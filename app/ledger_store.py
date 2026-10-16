"""Storage for the ledger. Same interface for both backends:

    save(rec) / get(user_id, decision_id) / list_for_user(user_id)

InMemoryLedger  -> local dev and tests
FirestoreLedger -> real storage (pip install google-cloud-firestore)

Firestore layout: users/{user_id}/decisions/{decision_id}
"""
from __future__ import annotations

from typing import Optional

from .ledger import DecisionRecord


def _safe_id(value: str) -> str:
    # user_id comes from the browser, so never let it build a path.
    if not value or "/" in value or len(value) > 128:
        raise ValueError("invalid id")
    return value


class InMemoryLedger:
    def __init__(self) -> None:
        self._data: dict = {}

    def save(self, rec: DecisionRecord) -> None:
        _safe_id(rec.user_id)
        self._data.setdefault(rec.user_id, {})[rec.id] = rec.to_dict()

    def get(self, user_id: str, decision_id: str) -> Optional[DecisionRecord]:
        d = self._data.get(_safe_id(user_id), {}).get(decision_id)
        return DecisionRecord.from_dict(d) if d else None

    def list_for_user(self, user_id: str) -> list:
        return [DecisionRecord.from_dict(d)
                for d in self._data.get(_safe_id(user_id), {}).values()]

    def delete(self, user_id: str, decision_id: str) -> None:
        self._data.get(_safe_id(user_id), {}).pop(decision_id, None)


class FirestoreLedger:
    def __init__(self, project: Optional[str] = None, client=None,
                 root: str = "users") -> None:
        if client is None:
            from google.cloud import firestore  # imported lazily
            client = firestore.Client(project=project)
        self._db = client
        self._root = root

    def _col(self, user_id: str):
        return (self._db.collection(self._root)
                .document(_safe_id(user_id)).collection("decisions"))

    def save(self, rec: DecisionRecord) -> None:
        self._col(rec.user_id).document(rec.id).set(rec.to_dict())

    def get(self, user_id: str, decision_id: str) -> Optional[DecisionRecord]:
        snap = self._col(user_id).document(decision_id).get()
        return DecisionRecord.from_dict(snap.to_dict()) if snap.exists else None

    def list_for_user(self, user_id: str) -> list:
        return [DecisionRecord.from_dict(s.to_dict())
                for s in self._col(user_id).stream()]

    def delete(self, user_id: str, decision_id: str) -> None:
        self._col(user_id).document(decision_id).delete()
