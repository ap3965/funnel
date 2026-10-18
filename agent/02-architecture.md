# 02: Architecture (rough draft, not finalized by the team)

> Written to get agents moving. If the human changes something, they will say so; update this file when they do. If you think a change is needed, propose it and ask: do not silently restructure.

## Shape
```
Browser (app/static/index.html, plain JS, no framework)
   |  X-User-Id header (random id in localStorage; ?user=demo-ravi for the seeded demo)
FastAPI (app/main.py)  ->  SessionManager (app/session.py)
                              |-- llm.py      Gemini: extract / next_turn / embed   (ONLY file that calls the model API)
                              |-- guard.py    rejects advice, plans, lists; regenerate up to 2x; then safe fallback question
                              |-- memory.py   MemoryService: one call prepares a session's memory
                              |     |-- matcher.py   SAME decision (topic) vs ECHO (similar worry)  [embeddings + cosine]
                              |     |-- patterns.py  counts facts in plain code -> text block for the prompt
                              |     |-- ledger.py / ledger_store.py   DecisionRecord; InMemoryLedger | FirestoreLedger
                              |-- prompts.py  interrogator + extractor prompts (the quality lives here)
```

## One session, in order
1. `POST /session {dump}` -> `llm.extract` gives `{decision, options, worries}`.
2. `memory.prepare(user, session, title, options, worries)`: embeds, finds a SAME decision (loop) or creates a new record; finds ECHOES from other concluded decisions using the **fresh** worries; `patterns.compute_facts` counts; `render_for_prompt` builds the block.
3. Interrogator system prompt = `INTERROGATOR_SYSTEM` + memory block. Full conversation history is sent every turn.
4. Reply passes `guard.check`. Hard problem: regenerate with the reasons (max 3 attempts), then a fixed safe question. Soft problem: allowed, logged.
5. After 8 model turns the turn carries `offer: true` once, which shows a small "Write it down" link. It never replaces the AI's question and never hides the answer box. The user can wrap up any time with "I know where I've landed".
6. `POST /session/{id}/wrap {text}` -> `llm.extract_commit` proposes `{conclusion_kind, conclusion, next_step, revisit_date}` from the user's free text (only what they said; saves nothing). The UI shows it for review.
7. `POST /session/{id}/commit` saves it (parked requires a date). A saved next step gets `step_status=open`.
8. Check-in: `GET /decisions` lists the user's open steps; `POST /decisions/{id}/step {done|not_yet|dropped}`; `POST /session/from-step {decision_id}` opens a session about a step marked not yet (`memory.reopen`, a returning mention, the step in the facts block).

## API (shapes are used by index.html: do not change without updating both)
| Route | Body | Returns |
|---|---|---|
| `POST /session` (header `X-User-Id`) | `{dump, direct_opt_in?}` | `{session_id, first_turn, memory}` |
| `POST /session/{id}/turn` | `{answer}` | `{type, text}` (`question` or `observation`, plus `offer: true` once) |
| `POST /session/{id}/wrap` | `{text}` | `{conclusion_kind, conclusion, next_step, revisit_date}` (proposal) |
| `POST /session/{id}/commit` | `{conclusion, conclusion_kind, next_step, revisit_date?}` | `{ok, decision_id}` |
| `POST /decisions/{id}/step` (header) | `{status: done\|not_yet\|dropped}` | `{decision_id, step_status}` |
| `POST /session/from-step` (header) | `{decision_id}` | `{session_id, first_turn, memory}` |
| `GET /decisions` (header) | | this user's ledger only |
| `GET /stats` | | guard counters for the deck |
| `GET /health`, `GET /` | | health (not `/healthz`: Google reserves that path on Cloud Run), the UI |

## Data model (`DecisionRecord`)
`id, user_id, title, worries[], options[], created_at, mentions[{session_id, at}], conclusion_kind (decided|need_more_info|parked), conclusion, next_step, step_status (open|done|not_yet|dropped), step_updated_at, revisit_date, outcome_note, seeded, topic_embedding, worry_embedding`. Firestore path: `users/{user_id}/decisions/{id}`. `times_raised = len(mentions)`.

## Guard (`app/guard.py`)
- **Hard (reject):** numbered/bulleted lines; plan wording; wrap-up lines ("Is there anything else?"); advice in statements ("you should", "I recommend", "my advice", "it's better to"); commands at the start of a sentence ("Try...", "Consider...", "Take..."); "why not try..."; more than 2 questions; over 120 words; `type=question` without a "?".
- **Soft (log only):** two questions; over 60 words; leading questions ("have you considered...", "what if you just...").
- Advice patterns are checked on non-question sentences only, so "Why do you think you should rewrite it?" passes. Test table: `tests/test_guard.py`.

## Memory rules
- Loop = same decision (topic similarity high, optional LLM tiebreak in the grey zone). Echo = different decision, similar worry, **and the past one has a conclusion**.
- Thresholds in `matcher.py` (0.85 / 0.70 / 0.60) are **guesses**. Tune with `python -m eval.run_match_eval` on real embeddings.
- Stance escalates by `times_raised`: 1 neutral; 2 name the loop; 3+ ask permission to be more direct; direct only after the user opts in (checkbox).
- If embedding or Firestore fails, the session still works (memory is skipped, logged). Commit says saving is unavailable.

## Config (env vars; see `.env.example`)
`GEMINI_API_KEY`, `GEMINI_MODEL` (default `gemini-3.8-flash`), `GEMINI_FALLBACK_MODEL`, `EMBED_MODEL` (`gemini-embedding-001`, 768 dims), `USE_FIRESTORE=1`, `GOOGLE_CLOUD_PROJECT`. Model names change often: `scripts/check_setup.py` shows what the key can use.

## Deployment
Cloud Run from `Dockerfile`. **Use `--max-instances 1`**: live conversations are held in server memory (sessions expire after 6 h or a restart; the UI handles that). Long-term data lives in Firestore. Public service (`--allow-unauthenticated`), so input limits and per-user isolation matter.

## Known limits (be honest about them)
Sessions are in-memory (single instance). No accounts: identity is a browser id. No rate limiting beyond input and turn caps. The `/stats` counters reset on restart. The matcher's accuracy is unmeasured until the eval is run on real embeddings.
