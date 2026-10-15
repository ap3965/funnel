"""First thing to run after setup:  python scripts/check_setup.py
Checks Python, your key, the models, embeddings and (if enabled) Firestore. Prints PASS/FAIL per step.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import config  # noqa: E402


def step(name, fn):
    try:
        detail = fn()
        print(f"PASS  {name}" + (f"  ->  {detail}" if detail else ""))
        return True
    except Exception as exc:                       # show the real error, not a stack trace
        print(f"FAIL  {name}  ->  {type(exc).__name__}: {str(exc)[:300]}")
        return False


def main() -> None:
    ok = [step("Python 3.11+", lambda: sys.version.split()[0] if sys.version_info >= (3, 11)
               else (_ for _ in ()).throw(RuntimeError("install Python 3.11 or newer")))]
    ok.append(step("GEMINI_API_KEY is set", lambda: "set" if config.GEMINI_API_KEY or config.USE_VERTEX
                   else (_ for _ in ()).throw(RuntimeError("add it to .env"))))
    if not ok[-1]:
        sys.exit(1)

    from app.llm import get_llm
    llm = get_llm()

    def models():
        names = [m.name.replace("models/", "") for m in llm._client.models.list()]
        flash = sorted(n for n in names if "flash" in n and "image" not in n and "tts" not in n)[:12]
        return f"configured: {config.GEMINI_MODEL} / fallback {config.GEMINI_FALLBACK_MODEL}; flash models seen: {flash}"

    ok.append(step("List models your key can use", models))
    ok.append(step(f"Generate with {config.GEMINI_MODEL}", lambda: llm.next_turn(
        "Reply as JSON.", [{"role": "user", "text": "Say hello."}])["text"][:60]))
    ok.append(step(f"Embed with {config.EMBED_MODEL}", lambda: f"{len(llm.embed(['hello'])[0])} dimensions"))
    if config.USE_FIRESTORE:
        from app.ledger_store import FirestoreLedger
        ok.append(step("Firestore reachable", lambda: f"{len(FirestoreLedger(project=config.GCP_PROJECT).list_for_user('__check__'))} docs"))
    print("\nAll good. Next: python -m pytest -q" if all(ok) else
          "\nFix the FAIL lines above, top to bottom. A model-name error: pick a name from the list and set GEMINI_MODEL in .env.")


if __name__ == "__main__":
    main()
