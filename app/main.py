"""HTTP API. Route paths and field names match the existing index.html.

POST /session              {dump, direct_opt_in?}  header X-User-Id  -> {session_id, first_turn, memory}
POST /session/{id}/turn    {answer}                                  -> {type, text}
POST /session/{id}/commit  {conclusion, conclusion_kind, next_step, revisit_date?} -> {ok, decision_id}
GET  /decisions            header X-User-Id                          -> this user's ledger
GET  /stats                                                          -> guard counters (for the deck)
GET  /healthz, GET /
"""
from __future__ import annotations

import os

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import FileResponse

from .logs import log_event
from .schemas import AnswerIn, CommitIn, StartIn
from .session import SessionManager

app = FastAPI(title="Funnel")
_INDEX = os.path.join(os.path.dirname(__file__), "static", "index.html")
_manager = None
_EMPTY_STATS = {"sessions_started": 0, "turns": 0, "guard_checked": 0, "guard_rejected": 0,
                "guard_soft": 0, "guard_fallbacks": 0, "commits": 0}


def get_manager() -> SessionManager:
    """Built on first use, so the app starts (and /healthz works) even before a key is set."""
    global _manager
    if _manager is None:
        from .llm import get_llm
        from .memory_factory import build_memory
        llm = get_llm()
        _manager = SessionManager(llm, build_memory(llm))
    return _manager


def _run(fn, *args):
    """Turn internal exceptions into short, plain messages for the user.
    Developer detail (error type, HTTP code, API message) goes to the logs only."""
    try:
        return fn(*args)
    except HTTPException:
        raise
    except KeyError:
        raise HTTPException(404, "This session expired. Please start again.")
    except ValueError as exc:                                 # our own input messages
        raise HTTPException(400, str(exc))
    except RuntimeError as exc:                               # e.g. "Saving is unavailable right now..."
        raise HTTPException(503, str(exc))
    except Exception as exc:                                  # model / network / Firestore / setup
        code = getattr(exc, "code", None)                     # HTTP status on Google API errors
        log_event("request_failed", error=type(exc).__name__, code=code, message=str(exc)[:300])
        if code == 429:
            raise HTTPException(503, "The demo has reached its free usage limit. Please try again in a minute.")
        raise HTTPException(502, "The assistant is unavailable right now. Please try again in a moment.")


@app.get("/health")
def healthz():
    return {"ok": True}


@app.post("/session")
def create_session(body: StartIn, x_user_id: str = Header(default="anon")):
    mgr = _run(get_manager)
    out = _run(mgr.start, x_user_id, body.dump, body.direct_opt_in)
    return {"session_id": out["session_id"], "first_turn": out["turn"], "memory": out["memory"]}


@app.post("/session/{session_id}/turn")
def session_turn(session_id: str, body: AnswerIn):
    mgr = _run(get_manager)
    return _run(mgr.answer, session_id, body.answer)["turn"]


@app.post("/session/{session_id}/commit")
def session_commit(session_id: str, body: CommitIn):
    mgr = _run(get_manager)
    revisit = body.revisit_date.isoformat() if body.revisit_date else None
    res = _run(mgr.commit, session_id, body.conclusion_kind, body.conclusion, body.next_step, revisit)
    return {"ok": True, "decision_id": res["decision_id"]}


@app.get("/decisions")
def list_decisions(x_user_id: str = Header(default="anon")):
    mgr = _run(get_manager)
    return _run(mgr.decisions, x_user_id)


@app.get("/stats")
def stats():
    return _manager.stats if _manager else _EMPTY_STATS


@app.get("/")
def index():
    return FileResponse(_INDEX)
