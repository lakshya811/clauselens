"""Single import point for the active LLM provider.

All app code calls get_llm() instead of importing GeminiProvider directly.
When a second provider (OpenAI, Anthropic, …) is added, only this file changes.
"""

from __future__ import annotations

from functools import lru_cache

from app.config import get_settings
from app.llm.gemini import GeminiProvider


@lru_cache(maxsize=1)
def get_llm() -> GeminiProvider:
    settings = get_settings()
    if not settings.has_llm_credentials:
        raise RuntimeError(
            "No LLM credentials configured. Set GOOGLE_API_KEY in .env."
        )
    return GeminiProvider(api_key=settings.google_api_key)
