"""
main.py — FastAPI app with the 4 routes from Section 9.
"""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app import session as sess
from app.schemas import Commit, Turn
from app.store import get_store

app = FastAPI(title="Funnel", version="0.1.0")

# Allow browser fetch from any origin (tighten for production if desired)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request bodies
# ---------------------------------------------------------------------------
class DumpBody(BaseModel):
    dump: str


class AnswerBody(BaseModel):
    answer: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/session", response_model=dict)
async def create_session(body: DumpBody):
    """POST /session  — start a new session with the user's raw dump."""
    if not body.dump.strip():
        raise HTTPException(status_code=400, detail="dump cannot be empty")
    session_id = str(uuid.uuid4())
    first_turn = sess.start_session(session_id, body.dump)
    return {"session_id": session_id, "first_turn": first_turn.model_dump()}


@app.post("/session/{session_id}/turn", response_model=Turn)
async def session_turn(session_id: str, body: AnswerBody):
    """POST /session/{id}/turn  — send the user's answer, get next Turn."""
    if not body.answer.strip():
        raise HTTPException(status_code=400, detail="answer cannot be empty")
    turn = sess.next_turn(session_id, body.answer)
    return turn


@app.post("/session/{session_id}/commit", response_model=dict)
async def session_commit(session_id: str, commit: Commit):
    """POST /session/{id}/commit  — save the user's conclusion to the ledger."""
    decision = sess.commit_session(session_id, commit)
    if not decision:
        raise HTTPException(status_code=404, detail="session not found")
    return {"ok": True, "decision_id": decision.id}


@app.get("/decisions")
async def list_decisions():
    """GET /decisions  — return the full ledger."""
    store = get_store()
    decisions = store.list_decisions()
    return [d.model_dump(mode="json") for d in decisions]


# ---------------------------------------------------------------------------
# Serve static index.html from project root
# ---------------------------------------------------------------------------
import os
from fastapi.responses import FileResponse

@app.get("/")
async def index():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "index.html")
    return FileResponse(path)
