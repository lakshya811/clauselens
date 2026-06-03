"""Clause extraction + risk flagging route.

POST /analyze/{doc_id} runs both analyses in sequence and returns the combined
AnalysisResponse. The two LLM calls are sequential (not concurrent) because:
  1. This keeps the implementation simple — no asyncio task management needed.
  2. The total latency (~4-6s on Gemini free tier) is acceptable for a
     document-level operation that a user triggers once per upload.
  3. If we needed to parallelize, we'd wrap both calls in asyncio.gather() —
     but that would also double our per-minute token quota usage.

Both calls are logged to the JSONL observability file with their individual
latency/tokens/cost, so the /metrics endpoint shows the full picture.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.analysis.extractor import extract_clauses
from app.analysis.risk_flagger import flag_risks
from app.config import get_settings
from app.llm.factory import get_llm
from app.observability.logger import log_request
from app.schemas.analysis import AnalysisResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/analyze", tags=["analysis"])


@router.post("/{doc_id}", response_model=AnalysisResponse, status_code=status.HTTP_200_OK)
async def analyze(request: Request, doc_id: str) -> AnalysisResponse:
    settings = get_settings()
    t_start = time.perf_counter()

    if not settings.has_llm_credentials:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Set GOOGLE_API_KEY in .env.",
        )

    docs = getattr(request.app.state, "documents", {})
    doc_entry = docs.get(doc_id)
    if doc_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{doc_id}' not found. Upload it first.",
        )

    parsed = doc_entry["parsed"]
    full_text = parsed.full_text

    llm = get_llm()

    clause_bundle, clause_obs = extract_clauses(
        text=full_text,
        doc_id=doc_id,
        llm=llm,
        model_cheap=settings.model_cheap,
        model_strong=settings.model_strong,
    )

    risk_report, risk_obs = flag_risks(
        text=full_text,
        doc_id=doc_id,
        llm=llm,
        model_cheap=settings.model_cheap,
        model_strong=settings.model_strong,
    )

    total_latency_ms = (time.perf_counter() - t_start) * 1000
    total_input = clause_obs["input_tokens"] + risk_obs["input_tokens"]
    total_output = clause_obs["output_tokens"] + risk_obs["output_tokens"]
    total_cached = clause_obs["cached_tokens"] + risk_obs["cached_tokens"]
    total_cost = clause_obs["cost_usd"] + risk_obs["cost_usd"]

    # Log a combined summary record for the /metrics endpoint
    request_id = log_request(
        route="/analyze/combined",
        model=f"{clause_obs['model']}+{risk_obs['model']}",
        routing_reason=f"extract:{clause_obs['routing_reason']},risk:{risk_obs['routing_reason']}",
        input_tokens=total_input,
        output_tokens=total_output,
        cached_tokens=total_cached,
        cost_usd=total_cost,
        latency_ms=total_latency_ms,
        doc_id=doc_id,
    )

    return AnalysisResponse(
        doc_id=doc_id,
        clauses=clause_bundle,
        risks=risk_report,
        model=f"{clause_obs['model']}+{risk_obs['model']}",
        input_tokens=total_input,
        output_tokens=total_output,
        cached_tokens=total_cached,
        cost_usd=round(total_cost, 8),
        latency_ms=round(total_latency_ms, 2),
        request_id=request_id,
    )
