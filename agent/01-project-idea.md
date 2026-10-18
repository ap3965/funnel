# 01: The project idea

## One line
Funnel helps people get unstuck on decisions they have been carrying around, using an AI that only asks questions, and remembers so it can notice patterns over time.

## The problem
People carry unresolved decisions for weeks. Common tools fail in two ways: to-do and productivity apps organize tasks but ignore why the person is stuck; chatbots hand out generic advice (the AI does the thinking) and forget everything next session. Research on procrastination describes avoidance as largely about managing the emotions a task or decision brings up. That research is about task avoidance and is largely correlational; **do not claim it proves Funnel works**. The evidence for Funnel is what real testers say and whether they come back.

## The solution (the loop)
1. **Dump**: the user pours out the decision, messy and unorganized.
2. **Discover**: the AI asks one question at a time (or one short observation). It finds what makes the decision hard: the feeling, the trade-off, a contradiction, an assumption. It quotes the user's own words.
3. **Decide**: the user reaches their own conclusion. Valid outcomes: decided, need more information, parked until a date. The AI never chooses.
4. **Move**: the user says where they landed in one free-text box. The AI only sorts what they said into a conclusion, a next step and a date (never inventing one); the user reviews it and saves. No long form.
   4b. **Check in** (pull, not push): when the user opens the app, "Your next steps" lists their own saved steps with Done / Not yet / Drop it. "Not yet" opens a questions-only session about it ("What got in the way?"). An optional "Remind me tonight" button downloads a calendar event the user controls.
5. **Revisit** (next session): Funnel uses the ledger. Two kinds of memory:
   - **Loop**: the same decision came back. ("This has come up 2 times. Last time you decided X. Your revisit date has passed.")
   - **Echo**: a different decision with a similar worry. ("Last time you were afraid of choosing wrong and tried a smaller version first. Does that change how you see this?")

## What makes it different from a chatbot
- It **cannot** give advice: a code-level guard rejects advice, plans, lists, and wrap-up lines.
- It **remembers**, per user, with counted facts. The AI never invents a pattern.
- It never tells the user who they are ("you are indecisive"). It asks whether a pattern still fits.
- It pulls, it does not push: no notifications.

## Demo persona
A solo developer or founder facing choices like "rewrite the backend or keep shipping". Seeded demo user: `?user=demo-ravi`.

## The demo moment (build everything around this)
Session 2: the user dumps a new dilemma. Funnel shows a "What I remembered" card and a timeline, and asks a question that connects it to a past decision in the user's own words. This must land in a 3-minute video.

## Google AI Builder Cup: how we are judged
- Technical merit & Gen AI use: **40%**. Meaningful, sound, scalable use of Gemini.
- Innovation & creativity: **25%**. Creative Gen AI beyond a basic or superficial implementation.
- Problem alignment & impact: **25%**. Fits the theme; clear value for a defined group of users.
- UX & solution design: **10%**.
- Deliverables: deployed prototype (Cloud Run), PDF deck, 3-minute video. Deadline Oct 18, 2026 (confirm the exact hour and time zone on the event page).
- Theme: Future of Work and enterprise productivity: decisions and workflow execution.

## What Funnel is NOT
Not a general to-do app, scheduler, or coach. The only tasks are the user's own next steps from a decision; the AI never writes them. Not a mental-health product: it does not diagnose, treat, or claim to reduce anxiety. No notifications. No methodology marketplace, no adaptive layouts (cut deliberately).

## Honest risks (do not hide these in the deck)
- The general "AI that asks questions" space is crowded; our edge is the guard plus the per-user ledger with loop and echo memory.
- Nothing yet shows that questioning helps people decide better. Evidence = 3 to 5 real testers across two sessions.
- Matching a reworded decision to its past self is the hardest technical part. Measure it (`eval/run_match_eval.py`) and report the real number.
- The strongest moment only appears in session 2, so seeded history is used. Label it as seeded.
