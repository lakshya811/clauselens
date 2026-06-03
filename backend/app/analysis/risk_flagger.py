"""Risk flagging using Gemini JSON mode + multi-step reasoning.

Interview answer:
  "Risk flagging requires legal reasoning — 'is this liability cap unusually low
  for this industry?' — so it goes to the strong model (flash). I give the model
  a specific risk taxonomy (uncapped liability, auto-renewal trap, broad IP
  assignment, unilateral amendment, restrictive non-compete, missing dispute
  resolution) as a system prompt so it produces actionable flags, not vague
  warnings. The response is a RiskReport: a list of RiskFlag objects each with
  severity/clause_reference/explanation/recommendation, plus an overall risk
  level and executive summary."

Model routing: TaskType.RISK → always strong model (multi-step legal inference).
"""

from __future__ import annotations

import logging

from app.llm.provider import LLMProvider, Message
from app.llm.router import TaskType, route
from app.observability.logger import log_request
from app.schemas.analysis import RiskReport, RiskSeverity

logger = logging.getLogger(__name__)

_MAX_CONTEXT_CHARS = 48_000

_SYSTEM_PROMPT = """You are a senior contract lawyer performing a risk review.
Identify risks in the following categories (but do not limit yourself to these):
  - Uncapped or asymmetric liability
  - Auto-renewal without adequate notice requirements
  - Broad or unilateral IP assignment to the other party
  - Unilateral amendment rights (one party can change terms without consent)
  - Overly restrictive non-compete or non-solicitation clauses
  - Missing or unfavourable dispute resolution / governing law
  - Ambiguous payment terms or undefined fees
  - Weak confidentiality or data protection obligations

For each risk: give it a short title, severity (high/medium/low), the specific
clause or section reference, a clear explanation, and a concrete negotiation
recommendation.

Return ONLY the JSON object. No markdown, no preamble."""

_USER_TEMPLATE = """Review the following contract for risks.

CONTRACT TEXT:
{text}
"""


def flag_risks(
    text: str,
    doc_id: str,
    llm: LLMProvider,
    model_cheap: str,
    model_strong: str,
) -> tuple[RiskReport, dict]:
    """Identify and rank risks in the contract.

    Returns:
        (RiskReport, obs_metadata)
    """
    model, routing_reason = route(TaskType.RISK, model_cheap, model_strong)
    context = text[:_MAX_CONTEXT_CHARS]
    user_msg = _USER_TEMPLATE.format(text=context)

    try:
        obj, resp = llm.complete_json(  # type: ignore[attr-defined]
            messages=[Message(role="user", content=user_msg)],
            model=model,
            schema=RiskReport,
            system_prompt=_SYSTEM_PROMPT,
        )
        report = obj if isinstance(obj, RiskReport) else RiskReport(**obj)
    except Exception as exc:
        logger.exception("Risk flagging failed for %s", doc_id)
        report = RiskReport(
            flags=[],
            overall_risk=RiskSeverity.HIGH,
            summary=f"Risk analysis failed: {exc}",
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
    return report, obs
