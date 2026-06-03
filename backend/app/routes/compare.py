"""Version comparison route.

POST /compare — accepts two doc_ids, runs a Structural/Semantic/Surface
classification of every change between the two uploaded contract versions,
and returns a CompareResponse with full change list + executive summary.

Design notes:
  - Both documents must be uploaded before comparing. The route validates this
    and returns 404 for either missing doc.
  - Uses TaskType.COMPARE → strong model (multi-step legal reasoning).
  - Sequential (not concurrent): we send both texts in one LLM call.
  - Logged to JSONL observability with doc_id = "a_id:b_id" for traceability.
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.analysis.comparator import compare_contracts
from app.config import get_settings
from app.llm.factory import get_llm
from app.observability.logger import log_request
from app.schemas.compare import CompareRequest, CompareResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/compare", tags=["compare"])


@router.post("", response_model=CompareResponse, status_code=status.HTTP_200_OK)
async def compare(request: Request, body: CompareRequest) -> CompareResponse:
    settings = get_settings()
    t_start = time.perf_counter()

    if not settings.has_llm_credentials:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Set GOOGLE_API_KEY in .env.",
        )

    docs = getattr(request.app.state, "documents", {})

    doc_a = docs.get(body.doc_id_a)
    if doc_a is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{body.doc_id_a}' not found. Upload it first.",
        )

    doc_b = docs.get(body.doc_id_b)
    if doc_b is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{body.doc_id_b}' not found. Upload it first.",
        )

    text_a: str = doc_a["parsed"].full_text
    text_b: str = doc_b["parsed"].full_text

    llm = get_llm()

    result, obs = compare_contracts(
        text_a=text_a,
        text_b=text_b,
        doc_id_a=body.doc_id_a,
        doc_id_b=body.doc_id_b,
        llm=llm,
        model_cheap=settings.model_cheap,
        model_strong=settings.model_strong,
    )

    total_latency_ms = (time.perf_counter() - t_start) * 1000

    request_id = log_request(
        route="/compare",
        model=obs["model"],
        routing_reason=obs["routing_reason"],
        input_tokens=obs["input_tokens"],
        output_tokens=obs["output_tokens"],
        cached_tokens=obs["cached_tokens"],
        cost_usd=obs["cost_usd"],
        latency_ms=total_latency_ms,
        doc_id=f"{body.doc_id_a}:{body.doc_id_b}",
    )

    return CompareResponse(
        doc_id_a=body.doc_id_a,
        doc_id_b=body.doc_id_b,
        result=result,
        model=obs["model"],
        input_tokens=obs["input_tokens"],
        output_tokens=obs["output_tokens"],
        cached_tokens=obs["cached_tokens"],
        cost_usd=round(obs["cost_usd"], 8),
        latency_ms=round(total_latency_ms, 2),
        request_id=request_id,
    )
