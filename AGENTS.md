# AGENTS.md: read this first, every task

You are helping build **Funnel** for the **Google AI Builder Cup 2026** (theme: Future of Work, due **Oct 18, 2026**). Google only: Gemini + FastAPI + Cloud Run + Firestore. Nothing else is in scope.

## What Funnel is (one paragraph)
A web app where a person dumps a decision they have been carrying in their head. An AI that is **only allowed to ask questions** (never advise, never plan) helps them see what makes it hard. They write their own conclusion and next step. A ledger remembers it, so next time Funnel can say "this has come back" or "last time you had a similar worry, and you chose X". Counted facts come from code; the AI only phrases them.

## Non-negotiable rules
1. The AI never gives advice, plans, task lists, options the user did not name, or labels about who the user is. `app/guard.py` enforces this in code. **Never weaken or delete a guard rule to make a test pass.** Ask the human first.
2. Every number or past event the AI mentions must come from `app/patterns.py` (counted by code). The model only phrases it.
3. "Need more information" and "parked" are valid outcomes, not failures.
4. Pull, not push. No notifications from us, no nagging, no streaks, no scorecards. The only reminder is a calendar file the USER chooses to download.
   The only "tasks" in the app are the user's OWN next steps from a decision, in their words. The AI never creates, suggests or ranks tasks. Check-ins use neutral buttons (Done / Not yet / Drop it): "not yet" is a normal answer, never a failure.
5. Each user's ledger is private (`X-User-Id`). Never expose another user's decisions.
6. **Never log what a user typed.** Log event names, counts, and the model's own rejected text only.
7. **Never commit secrets.** `.env` is git-ignored. Never print API keys.
8. Seeded demo data is always flagged `seeded=True` and labelled in the UI. Never present it as real.

## Stack and commands
Python 3.11+, FastAPI, `google-genai` (Gemini), Firestore, Cloud Run, plain-JS UI in `app/static/index.html`.
```
source .venv/bin/activate
python scripts/check_setup.py        # key, models, embeddings, Firestore
python -m pytest -q                  # must stay green
uvicorn app.main:app --reload --port 8080
python -m eval.run_eval              # real model: first question for 10 dumps + guard numbers
python -m eval.run_match_eval        # real embeddings: matcher accuracy
python -m scripts.seed --user demo-ravi
```

## Where to look
- `agent/01-project-idea.md`: the whole idea, users, demo moment, judging criteria.
- `agent/02-architecture.md`: modules, data flow, API, data model (rough draft: see its header).
- `agent/03-plan-and-quality.md`: what to build, in what order, and the quality bar.
Read all three before starting any task that changes behaviour.

## Working agreements
- **Quality over quantity.** Fewer features, each reliable. Do not add features that are not in `agent/03-plan-and-quality.md`.
- Small steps. After each change run `python -m pytest -q` and say what passed or failed, honestly. Never claim something works unless you ran it.
- Write a test first for any new behaviour in `guard.py`, `patterns.py`, `matcher.py`, `memory.py`, `session.py`.
- Do not add dependencies, rename modules, or change the API shape without asking the human.
- The prompts in `app/prompts.py` are the product. When you change one, run `python -m eval.run_eval` and show the human the questions before and after.
- If something is unclear or conflicts with these docs, ask. Do not guess.
