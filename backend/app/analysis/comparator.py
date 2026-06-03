"""Contract version comparison using Gemini JSON mode.

Interview answer:
  "Comparing two contract versions is harder than a text diff because legal
  meaning isn't line-aligned. 'Licensor shall use reasonable efforts' vs
  'Licensor shall use best efforts' is a single word change with major legal
  consequences. I send both contract texts to the strong model with a
  taxonomy (Structural/Semantic/Surface) and let it identify clause-level
  changes. The structured output — a list of ChangedClause objects — can then
  be rendered as a side-by-side redline in the UI.

  I use TaskType.COMPARE → strong model because this requires multi-step
  legal reasoning: the model must locate corresponding clauses across versions,
  determine whether the legal meaning changed, and assess which party benefits."

Context window strategy: first 24k chars per version (total ~48k, fitting in
one Gemini call). For very long contracts this is a reasonable first-pass;
a production system would chunk+compare section-by-section.
"""

from __future__ import annotations

import logging

from app.llm.provider import LLMProvider, Message
from app.llm.router import TaskType, route
from app.observability.logger import log_request
from app.schemas.compare import CompareResult

logger = logging.getLogger(__name__)

_MAX_CHARS_PER_VERSION = 24_000

_SYSTEM_PROMPT = """You are a senior contract lawyer performing a redline review.
You will be given two versions of a contract — Version A (original) and
Version B (revised). Your job is to identify every meaningful change between
them and classify each change as:

  structural — a clause was added, removed, or so substantially rewritten that
               it represents a new or deleted obligation
  semantic   — the clause is still present but its legal meaning changed
               (e.g. "reasonable efforts" → "best efforts", narrowed scope,
               new party, changed amount or date, altered right/obligation)
  surface    — wording, punctuation, or formatting changed but legal effect
               is identical

For each change:
  - Identify the clause/section reference
  - Quote the relevant old text (from A) and new text (from B)
  - Explain why it matters legally and which party it favours
  - Note any change in risk exposure

After listing all changes, provide:
  - Accurate counts of structural / semantic / surface changes
  - A 2-3 sentence executive summary of the most significant changes
  - Which party (if either) benefits overall from Version B vs Version A

Return ONLY the JSON object. No markdown, no preamble."""

_USER_TEMPLATE = """Compare these two contract versions.

VERSION A (original):
{text_a}

---

VERSION B (revised):
{text_b}
"""


def compare_contracts(
    text_a: str,
    text_b: str,
    doc_id_a: str,
    doc_id_b: str,
    llm: LLMProvider,
    model_cheap: str,
    model_strong: str,
) -> tuple[CompareResult, dict]:
    """Classify changes between two contract versions.

    Returns:
        (CompareResult, obs_metadata)
    """
    model, routing_reason = route(TaskType.COMPARE, model_cheap, model_strong)
    ctx_a = text_a[:_MAX_CHARS_PER_VERSION]
    ctx_b = text_b[:_MAX_CHARS_PER_VERSION]
    user_msg = _USER_TEMPLATE.format(text_a=ctx_a, text_b=ctx_b)

    try:
        obj, resp = llm.complete_json(  # type: ignore[attr-defined]
            messages=[Message(role="user", content=user_msg)],
            model=model,
            schema=CompareResult,
            system_prompt=_SYSTEM_PROMPT,
        )
        result = obj if isinstance(obj, CompareResult) else CompareResult(**obj)

        # Recompute counts from the actual changes list in case the model
        # populated changes but got the counts wrong.
        if result.changes:
            result.structural_count = sum(
                1 for c in result.changes if c.change_type.value == "structural"
            )
            result.semantic_count = sum(
                1 for c in result.changes if c.change_type.value == "semantic"
            )
            result.surface_count = sum(
                1 for c in result.changes if c.change_type.value == "surface"
            )
    except Exception as exc:
        logger.exception("Version comparison failed for %s vs %s", doc_id_a, doc_id_b)
        result = CompareResult(
            changes=[],
            summary=f"Version comparison failed: {exc}",
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
    log_request(
        route="/compare",
        doc_id=f"{doc_id_a}:{doc_id_b}",
        **obs,
    )
    return result, obs
