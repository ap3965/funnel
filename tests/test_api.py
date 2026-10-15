"""HTTP-level smoke tests. NOTE: these were written without being able to run FastAPI,
so if one fails, read the error before assuming the app is wrong."""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.ledger_store import InMemoryLedger  # noqa: E402
from app.matcher import Matcher, fake_embed  # noqa: E402
from app.memory import MemoryService  # noqa: E402
from app.session import SessionManager  # noqa: E402
from tests.test_session import FakeLLM  # noqa: E402


def _client():
    llm = FakeLLM()
    main._manager = SessionManager(llm, MemoryService(InMemoryLedger(), Matcher(fake_embed)))
    return TestClient(main.app)


def test_health_and_index():
    c = _client()
    assert c.get("/healthz").json() == {"ok": True}
    assert c.get("/").status_code == 200


def test_session_turn_commit_flow():
    c = _client()
    r = c.post("/session", json={"dump": "I cannot decide."}, headers={"X-User-Id": "u1"})
    assert r.status_code == 200
    body = r.json()
    assert body["first_turn"]["text"].endswith("?") and "session_id" in body
    sid = body["session_id"]
    assert c.post(f"/session/{sid}/turn", json={"answer": "Fear, mostly."}).json()["type"] == "question"
    ok = c.post(f"/session/{sid}/commit", json={"conclusion": "Ship first", "conclusion_kind": "decided",
                                                "next_step": "Tomorrow 10am"})
    assert ok.json()["ok"] is True
    rows = c.get("/decisions", headers={"X-User-Id": "u1"}).json()
    assert rows[0]["conclusion"] == "Ship first" and rows[0]["conclusion_kind"] == "decided"


def test_ledger_is_private_per_user():
    c = _client()
    c.post("/session", json={"dump": "mine"}, headers={"X-User-Id": "alice"})
    assert len(c.get("/decisions", headers={"X-User-Id": "alice"}).json()) == 1
    assert c.get("/decisions", headers={"X-User-Id": "bob"}).json() == []


def test_errors_are_plain_and_correct():
    c = _client()
    assert c.post("/session/nope/turn", json={"answer": "hi"}).status_code == 404
    assert c.post("/session", json={"dump": "   "}, headers={"X-User-Id": "u1"}).status_code in (400, 422)
    sid = c.post("/session", json={"dump": "x"}, headers={"X-User-Id": "u1"}).json()["session_id"]
    parked = c.post(f"/session/{sid}/commit", json={"conclusion": "later", "conclusion_kind": "parked"})
    assert parked.status_code == 400
    assert c.post(f"/session/{sid}/commit", json={"conclusion": "x", "conclusion_kind": "maybe"}).status_code == 422


def test_stats_endpoint():
    c = _client()
    c.post("/session", json={"dump": "x"}, headers={"X-User-Id": "u1"})
    assert c.get("/stats").json()["guard_checked"] >= 1
