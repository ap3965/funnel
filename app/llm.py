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
from .prompts import COMMIT_EXTRACTOR_SYSTEM, EXTRACTOR_SYSTEM
from .retry import run_with_fallback
from .schemas import CommitExtractionOut, ExtractionOut, TurnOut


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
                raise EnvironmentError("GEMINI_API_KEY is not set. Copy .env.example to .env and add your key.")
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

        def attempt(model: str):
            resp = self._client.models.generate_content(
                model=model, contents=self._contents(messages), config=cfg)
            return schema.model_validate_json(resp.text)

        def note(model, n, exc):
            log_event("model_call_failed", model=model, attempt=n, error=type(exc).__name__,
                      code=getattr(exc, "code", None), message=str(exc)[:300])

        models = list(dict.fromkeys([config.GEMINI_MODEL, config.GEMINI_FALLBACK_MODEL]))
        return run_with_fallback(attempt, models, on_error=note)

    # -- public API ---------------------------------------------------------------
    def extract(self, dump: str) -> dict:
        out = self._generate(EXTRACTOR_SYSTEM, [{"role": "user", "text": dump}],
                             ExtractionOut, temperature=0.2)
        return out.model_dump()

    def extract_commit(self, text: str, today_iso: str) -> dict:
        out = self._generate(COMMIT_EXTRACTOR_SYSTEM.format(today=today_iso),
                             [{"role": "user", "text": text}], CommitExtractionOut, temperature=0.1)
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
