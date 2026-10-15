"""All settings come from environment variables (see .env.example)."""
from __future__ import annotations

import os

try:                                    # optional: reads .env when running locally
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _env(name: str, default=None):
    value = os.getenv(name)
    return value if value not in (None, "") else default


# --- Gemini -----------------------------------------------------------------
GEMINI_API_KEY = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")
USE_VERTEX = str(_env("GOOGLE_GENAI_USE_VERTEXAI", "")).lower() in ("1", "true", "yes")
VERTEX_LOCATION = _env("GOOGLE_CLOUD_LOCATION", "global")

# Model names change often. Run `python scripts/check_setup.py` to see what your key can use.
GEMINI_MODEL = _env("GEMINI_MODEL", "gemini-3.8-flash")
GEMINI_FALLBACK_MODEL = _env("GEMINI_FALLBACK_MODEL", "gemini-2.5-flash")
EMBED_MODEL = _env("EMBED_MODEL", "gemini-embedding-001")
EMBED_DIM = int(_env("EMBED_DIM", "768"))

# --- Storage ----------------------------------------------------------------
USE_FIRESTORE = _env("USE_FIRESTORE") == "1"
GCP_PROJECT = _env("GOOGLE_CLOUD_PROJECT")

# --- Limits (protect the API quota) -------------------------------------------
MAX_DUMP_CHARS = 4000
MAX_ANSWER_CHARS = 2000
MAX_FIELD_CHARS = 1000
SESSION_TTL_SECONDS = 6 * 60 * 60
MAX_SESSIONS = 500
