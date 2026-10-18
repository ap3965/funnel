# user-instructions: set up Funnel from zero (Mac + Homebrew)

Do the steps in order. After each step there is a **check**: if it fails, stop and fix it before going on.
Lines starting with `$` are typed into Terminal (without the `$`). Anything in `<angle brackets>` is for you to replace.

---
## Do I need Python notebooks or Google Colab?
**No.** Funnel is a normal web app (Python files + one HTML page) that runs on Google Cloud Run. Colab/notebooks are for experiments and cannot host the app. For trying prompts in the browser use Google AI Studio (optional). Everything below uses plain files.

---
## PART A: Check your tools (10 min)

**A1. Open Terminal.** Press `Cmd + Space`, type `Terminal`, press Enter.

**A2. Check Homebrew:** `$ brew --version`  → should print a version. (If "command not found", install from https://brew.sh and come back.)

**A3. Check Python (need 3.11 or newer):** `$ python3 --version`
- If it prints 3.11 / 3.12 / 3.13: good.
- If older or "command not found": `$ brew install python@3.12`, then close and reopen Terminal and check again.

**A4. Check Git:** `$ git --version`  → if missing: `$ brew install git`

**A5. Check Google Cloud CLI:** `$ gcloud --version`
- If "command not found": `$ brew install --cask gcloud-cli`
- If Homebrew says it cannot find that: `$ brew search gcloud` and install the cask it lists (older name: `google-cloud-sdk`).
- Close and reopen Terminal, run `gcloud --version` again.

**A6. Install Antigravity** (Google's IDE): search "Google Antigravity download", use Google's official page, install the Mac app, open it once and sign in with your Google account. (Or try `$ brew search antigravity` to see if there is a cask.)

**Check:** A2 to A5 each printed a version number.

---
## PART B: Get the project and open it (10 min)

**B1.** Find `funnel-V1.zip` in Finder (probably Downloads). Double-click it. A folder `funnel-V1` appears.

**B2. Move it somewhere permanent:**
```
$ mkdir -p ~/Projects
$ mv ~/Downloads/funnel-V1 ~/Projects/
```
**B3. Open it in Antigravity:** open Antigravity → `File` → `Open Folder…` → choose `Projects` → `funnel-V1` → `Open`. If it asks "Do you trust the authors?", choose Yes.

**B4. Open a terminal inside Antigravity:** menu `Terminal` → `New Terminal`. All commands from here on are typed in **that** terminal (it starts inside the project folder). Check: `$ pwd` ends with `funnel-V1`.

**B5. Hidden files:** names starting with a dot (`.env`, `.gitignore`) are hidden in Finder. Press `Cmd + Shift + .` to show them. Antigravity shows them already.

---
## PART C: Install and run (15 min)

**C1. Make an isolated Python environment and install everything:**
```
$ python3 -m venv .venv
$ source .venv/bin/activate
$ pip install -r requirements-dev.txt
```
(You must run `source .venv/bin/activate` every time you open a new terminal. You will see `(.venv)` at the start of the line.)
**Check:** the last line says "Successfully installed …". If `pip` errors, copy the full message to me.

**C2. Get a Gemini API key:** open https://aistudio.google.com/apikey → sign in → "Create API key" → copy it.

**C3. Put the key in `.env`:**
```
$ cp .env.example .env
```
In Antigravity open `.env` (left file list), replace `paste_your_key_here` with your key, save (`Cmd + S`). Never share this file, never commit it (git already ignores it).

**C4. Check everything:** `$ python scripts/check_setup.py`
You want PASS on every line. If the "Generate" line fails with a model-not-found error, look at the model list it printed, pick a flash model name from it, and add `GEMINI_MODEL=<that name>` to `.env`. Run the check again.

**C5. Run the tests:** `$ python -m pytest -q`  → all passing (the API tests may run for the first time on your machine: if one of those fails, send me the message).

**C6. Start the app:** `$ uvicorn app.main:app --reload --port 8080`
Open http://localhost:8080 in your browser. Write a few messy sentences about a real decision, press Start, answer 2 or 3 questions, press "I know where I've landed", fill the form, Save. Press **Ledger ↗** to see it.
**Check:** questions are specific to what you wrote and never contain advice. Stop the server with `Ctrl + C`.

**C7. Try the demo memory** (in memory only, for a quick look):
```
$ python -m scripts.seed
```
This seeds 3 labelled demo decisions, but in memory they vanish when the script ends. The real demo data goes into Firestore in Part E.

---
## PART D: Check your Antigravity agents understand the project (5 min)

The agents read `AGENTS.md` and the `agent/` folder. Open the agent panel in Antigravity and paste:

> Read AGENTS.md and the three files in the agent/ folder. In 5 lines: what is Funnel, what must you never do, and what is the first thing on the plan?

**Check:** the answer mentions "only asks questions", the guard, per-user privacy, and "never commit secrets". If it does not seem to have read them, paste: "Open and read AGENTS.md now, then answer again." If it still ignores them, tell me. (Antigravity's folder conventions change between versions.)

Good first tasks to give an agent, one at a time:
1. "Run `python -m pytest -q` and report the result. Do not change any code."
2. "Run `python -m eval.run_eval` and show me all 10 first questions. Do not change code yet."
3. "Read the questions from the eval. Which are generic? Propose edits to `app/prompts.py` only. Show before/after questions."

---
## PART E: GitHub (10 min)

Your repo already exists: https://github.com/ap3965/funnel (it holds the earlier version). This command sequence puts the new project on top of it, keeping the history.

**E1. One-time Git identity** (skip if done before):
```
$ git config --global user.name "Your Name"
$ git config --global user.email "you@example.com"
```
**E2. Before the first commit, make sure no secret will be uploaded:**
```
$ git status
$ git grep -n "AIza" || echo "no key found in tracked files"
```
`.env` must NOT appear in `git status` after step E3. (If you ever push a key by accident: revoke it in AI Studio first, then ask me how to clean up.)

**E3. Connect and push:**
```
$ git init -b main
$ git remote add origin https://github.com/ap3965/funnel.git
$ git fetch origin
$ git reset --soft origin/main
$ git add -A
$ git status
$ git commit -m "V1: working backend, per-user ledger, stronger guard, safer UI"
$ git push -u origin main
```
GitHub may ask you to log in (use a Personal Access Token as the password, or sign in through the browser prompt). If any command errors, copy the message to me.

**E4. Add your partner:** github.com → the repo → Settings → Collaborators → Add people. For teamwork use one branch per task: `git switch -c feat/<what>` … then a Pull Request on GitHub.

---
## PART F: Google Cloud: Firestore + Cloud Run (30–45 min)

**F1. Log in:** `$ gcloud auth login` (a browser opens; use your Google account).
**F2. Choose or create a project** at https://console.cloud.google.com → project picker → New project (note the **Project ID**). **Link a billing account** to it (Billing menu). Cloud Run and Firestore need billing enabled (there are free allowances).
**F3. Point the CLI at it:**
```
$ gcloud config set project <PROJECT_ID>
```
**F4. Turn on the services:**
```
$ gcloud services enable run.googleapis.com cloudbuild.googleapis.com firestore.googleapis.com artifactregistry.googleapis.com
```
**F5. Create the database** (one time):
```
$ gcloud firestore databases create --location=asia-south1 --type=firestore-native
```
If it rejects the location, run `gcloud firestore locations list` and use one from the list.

**F6. Deploy:** (put your real key and project id in; this command is long, paste it as one line or keep the backslashes)
```
$ gcloud run deploy funnel --source . --region asia-south1 --allow-unauthenticated --max-instances 1 \
  --set-env-vars GEMINI_API_KEY=<YOUR_KEY>,USE_FIRESTORE=1,GOOGLE_CLOUD_PROJECT=<PROJECT_ID>
```
- It may ask to create an Artifact Registry repository: answer `Y`.
- `--max-instances 1` is required (live conversations are kept in the server's memory).
- Your key will sit in your shell history and the service settings. That is acceptable for a hackathon; do not share screenshots of it. Revoke the key after the event.

**F7. Check:** the command prints a `Service URL`. Then:
```
$ curl <SERVICE_URL>/health         # should print {"ok":true}
```
Open the URL on your phone. Do one full session.

**F8. If saving or the ledger fails with a permission error,** give the service account access to Firestore:
```
$ gcloud projects describe <PROJECT_ID> --format="value(projectNumber)"
$ gcloud projects add-iam-policy-binding <PROJECT_ID> \
    --member="serviceAccount:<PROJECT_NUMBER>-compute@developer.gserviceaccount.com" \
    --role="roles/datastore.user"
```
**F9. Load the demo data into Firestore** (run from your project folder, with `.venv` active):
```
$ USE_FIRESTORE=1 GOOGLE_CLOUD_PROJECT=<PROJECT_ID> python -m scripts.seed --user demo-ravi
```
(This uses your own login. If it complains about credentials run `gcloud auth application-default login` first.)
Then open `<SERVICE_URL>/?user=demo-ravi` and dump: *"I keep going back and forth on whether to rewrite the backend in Go or keep shipping on the Python monolith. I'm scared of choosing wrong."*
**Check:** a "What I remembered" card appears ("This decision has come up 2 times…") and shows the seeded-demo label.

---
## PART G: Update the deployed app after changes
```
$ python -m pytest -q          # must be green first
$ gcloud run deploy funnel --source . --region asia-south1
```
(Settings from F6 are remembered; you only repeat them if you change them.)

---
## When something goes wrong
| You see | Do this |
|---|---|
| `command not found: python` | Use `python3`, or activate the env: `source .venv/bin/activate` |
| `ModuleNotFoundError` | Environment not active, or install missing: `source .venv/bin/activate && pip install -r requirements-dev.txt` |
| `GEMINI_API_KEY is not set` | `.env` missing or key not saved. Re-do C3. |
| 403 / "API key not valid" | Wrong key. Create a new one (C2). |
| model not found / 404 on the model | Run `python scripts/check_setup.py`, pick a model from its list, set `GEMINI_MODEL` in `.env`. |
| `Address already in use` (port 8080) | Another server is running. Close that terminal, or use `--port 8081`. |
| Questions all look generic | Normal on the first try. Run `python -m eval.run_eval` and ask an agent to improve `app/prompts.py` (Part D, task 3). |
| Cloud Run: billing / permission error | F2 billing link; F4 services; F8 IAM. |
| "This session expired" in the app | Normal after a restart or 6 hours. Press start again. |
| Anything else | Copy the **whole** error text and send it to me. |

## Rhythm for the last two days
Oct 16: Parts A to F done, deployed. Oct 17: question quality, memory check on real embeddings, seed Firestore, 3 testers, deck, video, submit tonight. Oct 18: buffer. Confirm the exact deadline hour and time zone on the event page today.
