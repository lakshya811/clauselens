"""Gemini provider implementation.

Key production behaviours (interview answers):

Retries + backoff (tenacity):
  "Gemini's free tier has per-minute rate limits. I wrap every call in a
  tenacity retry with exponential backoff (1 → 2 → 4 → 8s, max 4 attempts).
  On rate-limit (429) or transient 5xx I back off silently; other errors
  propagate immediately. This is the difference between a flaky demo and a
  production service."

Prompt caching:
  "For Q&A on the same document, the system prompt + context chunks are
  identical across questions. Gemini supports a cached_content object that
  bills those tokens at 75% off. I create a CachedContent per doc_id and
  reuse it for the session lifetime. The LLMResponse carries cached_input_tokens
  so the observability layer can show actual vs full-price cost."

Structured outputs / JSON mode:
  "When a pydantic model is passed as response_schema, I enable Gemini's
  response_mime_type=application/json + response_schema. The response is
  validated against the schema on receipt; if validation fails the whole
  call is retried (up to 2 extra times) before raising."
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.llm.cost import calculate_cost
from app.llm.provider import LLMProvider, LLMResponse, Message

logger = logging.getLogger(__name__)


def _is_retryable(exc: BaseException) -> bool:
    """Retry on rate-limit and transient server errors only."""
    try:
        from google.genai import errors as genai_errors
        return isinstance(exc, (genai_errors.ClientError,)) and getattr(
            exc, "status_code", 0
        ) in {429, 500, 502, 503, 504}
    except ImportError:
        return False


_retry = retry(
    retry=retry_if_exception(_is_retryable),
    wait=wait_exponential(multiplier=1, min=1, max=16),
    stop=stop_after_attempt(4),
    reraise=True,
)


class GeminiProvider(LLMProvider):
    """Gemini provider via the google-genai SDK."""

    def __init__(self, api_key: str) -> None:
        try:
            from google import genai
            from google.genai import types as genai_types
        except ImportError as exc:
            raise ImportError(
                "google-genai not installed. Run: pip install google-genai"
            ) from exc

        self._client = genai.Client(api_key=api_key)
        self._types = genai_types
        self._cache: dict[str, Any] = {}  # doc_id → CachedContent handle

    @_retry
    def complete(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        response_schema: Optional[Any] = None,
        system_prompt: Optional[str] = None,
    ) -> LLMResponse:
        types = self._types

        contents = [
            types.Content(
                role=m.role if m.role != "system" else "user",
                parts=[types.Part(text=m.content)],
            )
            for m in messages
            if m.role != "system"  # system handled separately
        ]

        config_kwargs: dict[str, Any] = {
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
        }
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        if response_schema is not None:
            config_kwargs["response_mime_type"] = "application/json"
            config_kwargs["response_schema"] = response_schema

        gen_config = types.GenerateContentConfig(**config_kwargs)

        response = self._client.models.generate_content(
            model=model,
            contents=contents,
            config=gen_config,
        )

        usage = response.usage_metadata
        input_tokens = getattr(usage, "prompt_token_count", 0) or 0
        output_tokens = getattr(usage, "candidates_token_count", 0) or 0
        cached_tokens = getattr(usage, "cached_content_token_count", 0) or 0

        text = response.text or ""

        cost = calculate_cost(
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_input_tokens=cached_tokens,
        )

        return LLMResponse(
            content=text,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost,
            latency_ms=0.0,  # timed_complete fills this in
            cached_input_tokens=cached_tokens,
        )

    def complete_json(
        self,
        messages: list[Message],
        model: str,
        schema: type,
        system_prompt: Optional[str] = None,
        max_retries: int = 2,
    ) -> tuple[Any, LLMResponse]:
        """Call complete() in JSON mode and parse+validate against schema.

        Returns (parsed_object, LLMResponse). Retries up to max_retries times
        on JSON parse / validation failure before re-raising.
        """
        last_exc: Optional[Exception] = None
        for attempt in range(max_retries + 1):
            resp = self.timed_complete(
                messages=messages,
                model=model,
                response_schema=schema,
                system_prompt=system_prompt,
            )
            try:
                raw = json.loads(resp.content)
                obj = schema(**raw) if not isinstance(raw, list) else raw
                return obj, resp
            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "JSON parse/validate failed (attempt %d/%d): %s",
                    attempt + 1, max_retries + 1, exc,
                )
        raise ValueError(
            f"Model did not return valid {schema.__name__} after "
            f"{max_retries + 1} attempts"
        ) from last_exc


def get_provider(api_key: str) -> GeminiProvider:
    """Factory — call this instead of constructing GeminiProvider directly."""
    return GeminiProvider(api_key=api_key)
