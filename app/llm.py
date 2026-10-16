"""Gemini wrapper. The ONLY file that talks to Google's model API.

Three methods are all the rest of the app needs:
    extract(dump)              -> {"decision", "options", "worries"}
    next_turn(system, messages) -> {"type", "text"}
    embed(texts)               -> list of vectors

messages: [{"role": "user" | "model", "text": "..."}]  (starts with "user")
"""
from __future__ import annotations

from . import config
from .logs import log_event
from .prompts import EXTRACTOR_SYSTEM
from .schemas import ExtractionOut, TurnOut


class GeminiLLM:
    def __init__(self) -> None:
        from google import genai            # imported here so tests never need the SDK
        from google.genai import types
        self._types = types
        if config.USE_VERTEX:
            self._client = genai.Client(vertexai=True, project=config.GCP_PROJECT,
                                        location=config.VERTEX_LOCATION)
        else:
            if not config.GEMINI_API_KEY:
                raise RuntimeError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
            self._client = genai.Client(api_key=config.GEMINI_API_KEY)

    # -- internals --------------------------------------------------------------
    def _contents(self, messages: list) -> list:
        t = self._types
        return [t.Content(role=m["role"], parts=[t.Part(text=m["text"])]) for m in messages]

    def _generate(self, system: str, messages: list, schema, temperature: float):
        t = self._types
        cfg = t.GenerateContentConfig(system_instruction=system,
                                      response_mime_type="application/json",
                                      response_schema=schema,
                                      temperature=temperature)
        last = None
        for model in dict.fromkeys([config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL]):
            try:
                resp = self._client.models.generate_content(
                    model=model, contents=self._contents(messages), config=cfg)
                return schema.model_validate_json(resp.text)
            except Exception as exc:                    # try the fallback model once
                last = exc
                log_event("model_call_failed", model=model, error=type(exc).__name__,
                          code=getattr(exc, "code", None), message=str(exc)[:300])
        raise last

    # -- public API ---------------------------------------------------------------
    def extract(self, dump: str) -> dict:
        out = self._generate(EXTRACTOR_SYSTEM, [{"role": "user", "text": dump}],
                             ExtractionOut, temperature=0.2)
        return out.model_dump()

    def next_turn(self, system: str, messages: list) -> dict:
        out = self._generate(system, messages, TurnOut, temperature=0.7)
        return out.model_dump()

    def embed(self, texts: list) -> list:
        t = self._types
        resp = self._client.models.embed_content(
            model=config.EMBED_MODEL, contents=texts,
            config=t.EmbedContentConfig(task_type="SEMANTIC_SIMILARITY",
                                        output_dimensionality=config.EMBED_DIM))
        return [list(e.values) for e in resp.embeddings]


_llm = None


def get_llm() -> GeminiLLM:
    global _llm
    if _llm is None:
        _llm = GeminiLLM()
    return _llm
