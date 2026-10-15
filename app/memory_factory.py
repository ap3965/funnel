"""Builds the MemoryService from environment settings."""
from __future__ import annotations

from . import config
from .ledger_store import FirestoreLedger, InMemoryLedger
from .matcher import Matcher
from .memory import MemoryService


def build_memory(llm) -> MemoryService:
    if config.USE_FIRESTORE:
        ledger = FirestoreLedger(project=config.GCP_PROJECT)
    else:
        ledger = InMemoryLedger()        # lost on restart: fine locally, NOT for the deployed demo
    return MemoryService(ledger, Matcher(llm.embed))
