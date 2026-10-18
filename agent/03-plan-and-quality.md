# 03: Plan and quality bar

**Today is Oct 16. Deadline Oct 18.** Quality over quantity: a small thing that works every time beats a big thing that sometimes does. Cut order if time runs short: direct-mode checkbox -> echo -> timeline polish. **Never cut:** the guard, the loop memory, the deployed app, the video.

## Milestones (each has a check: do not move on until it passes)
**M0: Runs locally (Oct 16, morning).** `check_setup.py` all PASS; `pytest` green; two sessions work in the browser. 
**M1: Deployed (Oct 16).** Cloud Run URL works from a phone with Firestore on; data survives a restart (`USE_FIRESTORE=1`). Do this BEFORE polishing: billing and permission problems always appear here.
**M2: Question quality (Oct 17, morning).** `python -m eval.run_eval`: read all 10 first questions. Each must be specific to its dump, under 45 words, no advice. Fix `prompts.py`, re-run, keep the before/after. Record the guard numbers.
**M3: Memory works on real embeddings (Oct 17).** `python -m eval.run_match_eval`: tune thresholds or add the LLM tiebreak; record accuracy. Seed Firestore (`USE_FIRESTORE=1 python -m scripts.seed`), open `?user=demo-ravi`, dump the backend-rewrite scenario: expect a loop card and an echo.
**M4: Evidence + submission (Oct 17).** 3 real testers, two sessions each, a few days apart if possible (else same day, clearly labelled). Deck (PDF), 3-minute video, README. Submit tonight; Oct 18 is buffer only.

## Already built (do not rebuild)
Guard, loop + echo memory, free-text wrap-up with review, next-steps check-in (Done / Not yet / Drop it), calendar reminder file, per-user ledger, plain-English voice.

## Technical work, in priority order
1. Keep tests green; fix anything real the first run reveals.
2. Prompt quality (`app/prompts.py`): this is the 40% + 25%.
3. Matcher accuracy on real embeddings; record the number.
4. Fact guard (valuable, small): verify that counts and dates in the AI's reply match the `Facts` block; reject replies that state numbers not in it.
5. UI: one calm screen flow, clear loading and error states, readable on a phone. The memory card and timeline are the demo frame; polish those, not extras.
6. Observability for the deck: `/stats` guard counters, structured logs.

## Quality bar
- Every question: specific, in the user's words, one at a time, no advice, no list, no label about the person.
- Every claim about the past: traceable to a counted fact.
- Errors are plain-language and recoverable (expired session, model failure, empty input).
- Mobile-readable, keyboard-usable, no HTML injection (user text only via `textContent`).
- No secrets in git or logs; no user text in logs.
- Honest evidence: report real numbers (guard blocked X of Y; matcher right on N of 20; K of 3 testers said a question surfaced something new). Say what is unproven.

## Do NOT build
Accounts/auth, notifications, methodology marketplace, adaptive layouts or themes, dashboards, settings pages, mobile app, multi-language, anything for another hackathon or stack.

## Agent working agreements
- One task at a time; small diffs; run `python -m pytest -q` after each; report real results.
- Show the human before/after question samples for any prompt change.
- Never edit a test to make it pass without telling the human why the test was wrong.
- Update `agent/02-architecture.md` if you change the architecture (after asking).
- When done, summarize: what changed, what you ran, what you did NOT verify.
