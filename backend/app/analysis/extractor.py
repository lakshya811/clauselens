"""Structured clause extraction using Gemini JSON mode.

Interview answer:
  "I pass the contract text to Gemini with response_schema=ClauseBundle, which
  forces the model to emit valid JSON conforming to that Pydantic schema.
  If the JSON fails Pydantic validation the GeminiProvider retries up to 2 times.
  I use the cheap model (flash-lite) for extraction because it's a
  fill-in-the-blanks task — no multi-step reasoning — and I've verified it
  matches flash accuracy on the CUAD sample contracts in the eval suite.
  The context window is the first 12,000 tokens of the contract (roughly 48KB),
  which covers all key clauses in typical commercial agreements without hitting
  the 1M-token context limit unnecessarily."

Fallback:
  If JSON mode fails after retries, we return a ClauseBundle with only the
  raw error in confidence_note — the caller gets a degraded but non-crashing
  response and the error is logged.
"""

from __future__ import annotations

import logging

from app.llm.provider import LLMProvider, Message
from app.llm.router import TaskType, route
from app.observability.logger import log_request
from app.schemas.analysis import ClauseBundle

logger = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 48_000  # ~12k tokens, covers key clauses in most contracts

_SYSTEM_PROMPT = """You are a precise contract analyst. Extract the requested
information from the contract text provided. Return ONLY the JSON object — no
markdown, no explanation. If a field is not present in the contract, use null.
Be conservative: extract verbatim phrases rather than paraphrasing."""

_USER_TEMPLATE = """Extract the key clauses from the following contract.

CONTRACT TEXT:
{text}
"""


def extract_clauses(
    text: str,
    doc_id: str,
    llm: LLMProvider,
    model_cheap: str,
    model_strong: str,
) -> tuple[ClauseBundle, dict]:
    """Extract structured clauses from contract text.

    Returns:
        (ClauseBundle, obs_metadata) — obs_metadata has model/tokens/cost for logging.
    """
    model, routing_reason = route(TaskType.EXTRACT, model_cheap, model_strong)
    context = text[:_MAX_CONTEXT_CHARS]
    user_msg = _USER_TEMPLATE.format(text=context)

    try:
        obj, resp = llm.complete_json(  # type: ignore[attr-defined]
            messages=[Message(role="user", content=user_msg)],
            model=model,
            schema=ClauseBundle,
            system_prompt=_SYSTEM_PROMPT,
        )
        bundle = obj if isinstance(obj, ClauseBundle) else ClauseBundle(**obj)
    except Exception as exc:
        logger.exception("Clause extraction failed for %s", doc_id)
        bundle = ClauseBundle(
            confidence_note=f"Extraction failed: {exc}"
        )
        resp = None

    obs = {
        "model": model,
        "routing_reason": routing_reason,
        "input_tokens": getattr(resp, "input_tokens", 0) if resp else 0,
        "output_tokens": getattr(resp, "output_tokens", 0) if resp else 0,
        "cached_tokens": getattr(resp, "cached_input_tokens", 0) if resp else 0,
        "cost_usd": getattr(resp, "cost_usd", 0.0) if resp else 0.0,
        "latency_ms": getattr(resp, "latency_ms", 0.0) if resp else 0.0,
    }
    log_request(route="/analyze", doc_id=doc_id, **obs)
    return bundle, obs
