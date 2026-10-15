# Funnel: Project Handoff

> For any AI assistant picking this up: this file is the source of truth. Do not re-brainstorm the idea. Help build, fix, and ship. Keep answers short and code-first; the user is on a free tier and the deadline is tight.

## 1. Deadline and scope
- **Google AI Builder Cup:** due **Oct 18, 2026**. Stack: Gemini + Cloud Run + Firestore. Theme: **Future of Work**.
- Google only. No other hackathon or stack is in scope right now.

## 2. The problem
People carry unresolved decisions in their heads for weeks. Chatbots give generic advice and forget everything next session. People need to see their own thinking clearly and notice patterns across decisions.

## 3. The solution
Funnel: dump a decision → AI only asks questions → you reach your own conclusion → saved to a ledger → session 2 surfaces patterns.

**Loop:** Dump → Discover (questions) → Decide (user's conclusion) → Move (user's next step, saved) → Revisit later.

## 4. Design rules (non-negotiable)
1. AI only asks questions. A **code-level guard** rejects advice/plans.
2. **Counted facts from code only.** No hallucinated "you always...".
3. Memory surfaces patterns but **never tells the user who they are**.
4. "Need more info" and "Parked" are valid outcomes.
5. **Pull, not push:** no notifications.

## 5. Architecture
```
Browser (index.html, plain JS)
   |
FastAPI (app/main.py)
   ├── session.py   turn loop: extract → match → guard → return
   ├── guard.py     regex/rules, retry once, log rejections
   ├── prompts.py   interrogator + extractor + observation prompts
   ├── llm.py       generate_text / generate_structured / embed  (Gemini)
   ├── matcher.py   worry-based similarity (embeddings + keyword fallback)
   ├── facts.py     pure code: counts, recurrence, days since
   └── store.py     MemoryStore (dev) | FirestoreStore (prod)
```

## 6. Data schemas (`app/schemas.py`)
- `Turn {type: "question"|"observation"|"offer_commit", text, decision_ids[]}`
- `Extraction {decision, worries[], options[]}`
- `Commit {conclusion, conclusion_kind: "decided"|"need_more_info"|"parked", next_step, revisit_date}`
- `Decision {id, created_at, dump, worries[], options[], conclusion, next_step, revisit_date, embedding?}`

## 7. Guard rules (`app/guard.py`)
**Hard reject:** numbered lists, advice verbs ("you should", "try", "consider", "I recommend"), closure phrases, invented options.
**Soft flag (log only):** forced-choice, leading questions.
On reject: retry once with stricter instruction → fall back to safe question. All rejections → `eval/rejections.log`.

**Known pitfall fixed:** closure regex was narrowed so `"anything else until you know?"` passes (see test case in `tests/test_guard.py`).

## 8. API routes
- `POST /session` → `{session_id, first_turn}`
- `POST /session/{id}/turn` → next `Turn`
- `POST /session/{id}/commit` → saves to ledger
- `GET /decisions` → ledger list

## 9. UI (`index.html`)
Three states, no framework:
1. **Dump** — big calm textarea, tagline: "I only ask questions. You decide."
2. **Discover** — one question at a time, memory card (filled session 2), guard badge
3. **Commit** — conclusion kind selector, next step, revisit date, timeline echo panel

Stats bar at bottom: guard rejections · turns · ledger entries.

## 10. Dev environment
Local Mac, Python 3.11+, VS Code. **Not Colab for the app.**

## 11. Google specifics
- Models: `gemini-3.8-flash` (text/structured), `gemini-embedding-001` (embeddings)
- API key via `GEMINI_API_KEY` env var — works on Cloud Run without Vertex
- Cloud Run + Firestore; secrets via env vars; never commit `.env`

---

## 12. ✅ What was built (Session 1 — Oct 15 2026)

All files created from scratch. No existing repo existed.

### Files created
| File | What it does |
|---|---|
| `app/schemas.py` | Pydantic models: Turn, Extraction, Commit, Decision |
| `app/llm.py` | Thin Gemini wrapper — `generate_text`, `generate_structured`, `embed` |
| `app/prompts.py` | Interrogator, Extractor, Observation system prompts |
| `app/guard.py` | Hard/soft regex rules, retry logic, rejection logger |
| `app/session.py` | Full turn loop wiring all modules together |
| `app/store.py` | Abstract interface + MemoryStore + FirestoreStore |
| `app/facts.py` | Pure-code fact computation (no LLM calls) |
| `app/matcher.py` | Cosine similarity matcher with keyword fallback |
| `app/main.py` | FastAPI app, 4 routes, serves `index.html` |
| `index.html` | 3-state UI, memory card, timeline, ledger overlay, stats bar |
| `tests/test_guard.py` | 15-case guard test table (12 verified passing) |
| `eval/dumps.json` | 10 hand-written decision dumps for eval |
| `seed_demo.py` | Seeds 2 labeled demo decisions for session-2 demo |
| `Dockerfile` | Cloud Run ready |
| `.gitignore`, `.env.example`, `requirements.txt`, `README.md` | Project config |

### Decisions made while building
1. **Model:** `gemini-3.8-flash` (not `gemini-2.5-flash` from earlier draft — that's deprecated). Confirmed from `gemini-api-dev` skill.
2. **Auth:** API key (`GEMINI_API_KEY`) not Vertex AI — works on Cloud Run, simpler for hackathon, avoids extra GCP wiring.
3. **SDK call style:** Used `client.models.generate_content` (not the new `interactions` API) because it supports JSON-mode structured output with `response_schema`, which is needed for `Extraction`.
4. **Session state:** In-memory dict in `session.py` (not Redis/Firestore for session) — safe for single Cloud Run instance, sufficient for demo.
5. **Guard closure regex:** Made deliberately narrow to avoid the known false-positive on `"anything else until you know?"` — this string is a must-pass test case.
6. **Store backend:** Selected by `STORE_BACKEND` env var (`"memory"` default, `"firestore"` for prod) — no code change needed to switch.
7. **Embeddings for matcher:** Embed the joined worry strings (not the full dump) — matches on worry similarity, not topic similarity, per spec.
8. **`offer_commit` trigger:** After 6 turns (`MAX_QUESTIONS = 6` in `session.py`) — not time-based, turn-count-based.

---

## 13. 🔜 Next steps (in order)

**Do these before anything else:**

1. **Create GitHub repo + push**
   ```bash
   git init && git add . && git commit -m "Funnel: initial scaffold"
   git branch -M main
   git remote add origin <your-repo-url>
   git push -u origin main
   ```

2. **Add API key and run locally**
   ```bash
   cp .env.example .env   # paste GEMINI_API_KEY
   python3 -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   python seed_demo.py
   uvicorn app.main:app --reload
   # open http://localhost:8000
   ```

3. **Verify the session-2 moment** — with seeded data loaded, dump the backend rewrite scenario and check the memory card appears.

4. **Run guard tests**
   ```bash
   pytest tests/test_guard.py -v
   ```

5. **Run the 10-dump eval** — pipe each dump in `eval/dumps.json` through `/session` and count guard rejections. Report as: *"guard blocked X of Y plan-like replies"*.

6. **Wire Firestore** — set `STORE_BACKEND=firestore` + `GOOGLE_CLOUD_PROJECT` and test `store.py` FirestoreStore path.

7. **Deploy to Cloud Run**
   ```bash
   gcloud run deploy funnel --source . --region us-central1 \
     --set-env-vars GEMINI_API_KEY=... --allow-unauthenticated
   ```

8. **Verify from a clean browser** (incognito, mobile) after deploy.

9. **Submission:** README ✅ · architecture diagram (draw from Section 5) · 3-min video · deck.

**Cut order if time runs out:** matcher accuracy test → timeline polish → Firestore. Never cut the guard, session-2 moment, or deploy.
