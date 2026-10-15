# Funnel

Google AI Builder Cup 2026 · Theme: Future of Work · Gemini + FastAPI + Cloud Run + Firestore

Funnel helps people get unstuck on decisions they have been carrying around. You dump the decision; an AI that is **only allowed to ask questions** (a code-level guard rejects advice and plans) helps you see what makes it hard; you write your own conclusion and next step. A per-user ledger remembers it, so next time Funnel can say "this decision has come back" or "last time you had a similar worry".

Start here: **`user-instructions.md`** (setup, run, deploy). For people and AI agents building it: `AGENTS.md` and `agent/`.

```
source .venv/bin/activate
python scripts/check_setup.py
python -m pytest -q
uvicorn app.main:app --reload --port 8080
```

| Piece | Where |
|---|---|
| Guard (advice/plan rejection) | `app/guard.py`, `tests/test_guard.py` |
| Counted facts (no hallucinated patterns) | `app/patterns.py` |
| Loop and echo matching | `app/matcher.py`, `app/memory.py` |
| Prompts | `app/prompts.py` |
| Evals | `eval/run_eval.py` (guard numbers, question quality), `eval/run_match_eval.py` (matcher accuracy) |
