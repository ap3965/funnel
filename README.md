# Funnel

> **Google AI Builder Cup 2026** · Theme: Future of Work · Stack: Gemini + FastAPI + Cloud Run + Firestore

## What it is

Funnel is a web app that helps you **see your own thinking clearly** on hard decisions.

- You dump a messy, unresolved decision
- The AI **only asks questions** — never plans, never advises
- You reach your own conclusion and write your own next step
- A **ledger** tracks decisions over time and surfaces patterns ("this worry has come up 3 times")

**The session-2 moment** — when a past decision echoes into today's — is the demo's key frame.

## Architecture

```
Browser (index.html, plain JS)
   |
FastAPI (app/main.py)
   ├── session.py   turn loop: extract → match → guard → return
   ├── guard.py     regex rules, retry once, log every rejection
   ├── prompts.py   interrogator + extractor + observation prompts
   ├── llm.py       generate_text / generate_structured / embed  (Gemini)
   ├── matcher.py   embedding-based worry similarity (cosine)
   ├── facts.py     pure code: counts, recurrence, days since
   └── store.py     MemoryStore (dev) | FirestoreStore (prod)
```

Models used: `gemini-3.8-flash` (text), `gemini-embedding-001` (embeddings).

## Guard (key differentiator)

Every AI response is checked against regex rules before it reaches the browser.

- **Hard reject:** advice verbs, numbered lists, invented options, closure phrases
- **Soft flag:** forced-choice or leading questions (logged, not rejected)
- On reject: retry once with stricter instruction → fall back to safe generic question
- All rejections logged to `eval/rejections.log`

See `tests/test_guard.py` for the 15-case test table.

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add your GEMINI_API_KEY
python seed_demo.py         # optional: seed 2 demo decisions
uvicorn app.main:app --reload
# open http://localhost:8000
```

## Tests

```bash
pytest tests/ -v
```

## Cloud Run deploy

```bash
gcloud run deploy funnel \
  --source . \
  --region us-central1 \
  --set-env-vars GEMINI_API_KEY=... \
  --allow-unauthenticated
```

For Firestore: `--set-env-vars STORE_BACKEND=firestore`

## What the judges will see

| Feature | Where |
|---|---|
| Guard working | `eval/rejections.log` + stats bar in UI |
| Memory ledger | Ledger button in UI |
| Session-2 echo | Memory card + timeline in Discover state |
| Code-counted facts | `facts.py` (no hallucination possible) |
| Seeded demo data | Labeled "seeded demo" in yellow in the UI |
