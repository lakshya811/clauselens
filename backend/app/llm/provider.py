"""Provider-agnostic LLM abstraction.

Design rationale (interview answer):
- A thin ABC decouples the rest of the app from any specific SDK. Swapping
  Gemini for OpenAI (or adding a third provider) requires only a new subclass
  and a config flag — no changes to analysis, RAG, or route code.
- LLMResponse carries latency, token counts, and pre-calculated cost so every
  call site gets observability data for free, without needing to know the
  provider's pricing table.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str


@dataclass
class LLMResponse:
    content: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: float
    cached_input_tokens: int = 0
    metadata: dict = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMProvider(ABC):
    """Abstract base for all LLM provider implementations."""

    @abstractmethod
    def complete(
        self,
        messages: list[Message],
        model: str,
        *,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
        response_schema: Optional[Any] = None,  # pydantic model → JSON mode
        system_prompt: Optional[str] = None,
    ) -> LLMResponse: ...

    def timed_complete(self, *args: Any, **kwargs: Any) -> LLMResponse:
        """Convenience wrapper that injects wall-clock latency into the response."""
        t0 = time.perf_counter()
        resp = self.complete(*args, **kwargs)
        resp.latency_ms = (time.perf_counter() - t0) * 1000
        return resp
