from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY not set in environment")
        _client = genai.Client(api_key=api_key)
    return _client


# ---------------------------------------------------------------------------
# Model names (current as of Oct 2026 per gemini-api-dev skill)
# ---------------------------------------------------------------------------
TEXT_MODEL = "gemini-3.8-flash"
EMBED_MODEL = "gemini-embedding-001"


def generate_text(
    system: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
) -> str:
    """Simple text generation. Returns the model's output as a string."""
    client = _get_client()
    # Build the turns list; the google-genai SDK expects a list of Content dicts
    # or a plain string. We construct a multi-turn conversation manually.
    history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        history.append({"role": role, "parts": [{"text": msg["content"]}]})

    last_user_msg = messages[-1]["content"]

    response = client.models.generate_content(
        model=TEXT_MODEL,
        contents=[
            *[types.Content(role=h["role"], parts=[types.Part(text=p["text"]) for p in h["parts"]]) for h in history],
            types.Content(role="user", parts=[types.Part(text=last_user_msg)]),
        ],
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
        ),
    )
    return response.text or ""


def generate_structured(
    system: str,
    messages: list[dict[str, str]],
    schema: type,
    temperature: float = 0.3,
) -> Any:
    """JSON-mode generation returning a parsed Pydantic model instance."""
    import json as _json
    from pydantic import TypeAdapter

    client = _get_client()
    history = []
    for msg in messages[:-1]:
        role = "user" if msg["role"] == "user" else "model"
        history.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))

    last_user_msg = messages[-1]["content"]

    response = client.models.generate_content(
        model=TEXT_MODEL,
        contents=[
            *history,
            types.Content(role="user", parts=[types.Part(text=last_user_msg)]),
        ],
        config=types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema,
        ),
    )
    raw = response.text or "{}"
    adapter = TypeAdapter(schema)
    return adapter.validate_json(raw)


def embed(texts: list[str]) -> list[list[float]]:
    """Return embeddings for a list of strings."""
    client = _get_client()
    result = client.models.embed_content(
        model=EMBED_MODEL,
        contents=texts,
    )
    return [e.values for e in result.embeddings]
