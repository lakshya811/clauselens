"""RAG-based Q&A route — citation-grounded answers over uploaded contracts.

Interview answer:
  "POST /ask takes a doc_id and question, runs hybrid retrieval (BM25 + vector,
  RRF, optional cross-encoder rerank), builds a context window from the top-k
  chunks, and calls the LLM with an explicit instruction to cite each claim with
  the chunk's clause heading and page number. The response carries the citations
  as structured objects — not just inline text — so the frontend can render them
  as clickable references. Every call is logged to the JSONL observability file
  with latency, token counts, cost, model, and retrieval hit count."

Degraded mode:
  - No API key → returns a 503 with a clear message (no silent empty answer).
  - Document not found → 404.
  - Retrieval returns 0 chunks → answers from LLM with an explicit note that
    no relevant context was found (avoids hallucination by design).
"""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, HTTPException, Request, status

from app.config import get_settings
from app.llm.factory import get_llm
from app.llm.provider import Message
from app.llm.router import classify_query_task, route
from app.observability.logger import log_request
from app.rag.embeddings import embed_query
from app.rag.retrieve import retrieve
from app.schemas.qa import AskRequest, AskResponse, CitedChunk

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ask", tags=["qa"])

_SYSTEM_PROMPT = """You are a precise contract analysis assistant.
Answer the user's question using ONLY the provided contract excerpts.
For every factual claim in your answer, cite the source using the citation label
supplied in square brackets at the start of each excerpt, e.g. [Section 4.2, p.7].
If the excerpts do not contain enough information to answer, say so explicitly —
do not speculate or use outside knowledge.
Be concise and professional."""


def _build_context(chunks_with_scores: list[tuple[object, float]]) -> str:
    """Format retrieved chunks as a numbered context block for the LLM prompt."""
    lines: list[str] = []
    for chunk, _score in chunks_with_scores:
        citation = getattr(chunk, "citation", f"chunk-{getattr(chunk, 'chunk_index', 0)}")
        text = getattr(chunk, "text", "")
        lines.append(f"[{citation}]\n{text}")
    return "\n\n---\n\n".join(lines)


@router.post("", response_model=AskResponse, status_code=status.HTTP_200_OK)
async def ask(request: Request, body: AskRequest) -> AskResponse:
    settings = get_settings()
    t_start = time.perf_counter()

    if not settings.has_llm_credentials:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LLM not configured. Set GOOGLE_API_KEY in .env.",
        )

    # Resolve document from app state
    docs = getattr(request.app.state, "documents", {})
    doc_entry = docs.get(body.doc_id)
    if doc_entry is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{body.doc_id}' not found. Upload it first.",
        )

    chunks = doc_entry["chunks"]
    top_k = body.top_k or settings.retrieval_top_k

    # Model routing
    task = classify_query_task(body.question)
    model, routing_reason = route(
        task,
        settings.model_cheap,
        settings.model_strong,
        query=body.question,
    )

    # Hybrid retrieval
    try:
        q_vec = embed_query(body.question, api_key=settings.google_api_key)
        vs = request.app.state.vector_store
        retrieved = retrieve(
            query=body.question,
            doc_id=body.doc_id,
            chunks=chunks,
            vector_store=vs,
            query_embedding=q_vec,
            top_k=top_k,
            rerank_n=settings.rerank_top_n,
        )
    except Exception:
        logger.exception("Retrieval failed for doc %s; falling back to BM25-only.", body.doc_id)
        # BM25-only fallback: build index from chunks and score directly
        from app.rag.retrieve import _bm25_ranked, _build_bm25

        bm25 = _build_bm25(chunks)
        retrieved = _bm25_ranked(bm25, chunks, body.question, top_k=top_k)

    retrieval_hits = len(retrieved)

    # Build prompt
    if retrieved:
        context = _build_context(retrieved)
        user_msg = (
            f"Contract excerpts:\n\n{context}\n\n"
            f"Question: {body.question}"
        )
    else:
        user_msg = (
            "No relevant contract excerpts were found for this question.\n\n"
            f"Question: {body.question}\n\n"
            "Please note that you have no contract text to draw from."
        )

    llm = get_llm()
    resp = llm.timed_complete(
        messages=[Message(role="user", content=user_msg)],
        model=model,
        system_prompt=_SYSTEM_PROMPT,
    )

    total_latency_ms = (time.perf_counter() - t_start) * 1000

    # Observability log
    request_id = log_request(
        route="/ask",
        model=model,
        routing_reason=routing_reason,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cached_tokens=resp.cached_input_tokens,
        cost_usd=resp.cost_usd,
        latency_ms=total_latency_ms,
        retrieval_hits=retrieval_hits,
        doc_id=body.doc_id,
    )

    # Build citation objects
    citations = [
        CitedChunk(
            chunk_index=getattr(chunk, "chunk_index", i),
            citation=getattr(chunk, "citation", f"chunk-{i}"),
            text_snippet=getattr(chunk, "text", "")[:200],
            score=round(float(score), 4),
        )
        for i, (chunk, score) in enumerate(retrieved)
    ]

    return AskResponse(
        answer=resp.content,
        citations=citations,
        model=model,
        routing_reason=routing_reason,
        input_tokens=resp.input_tokens,
        output_tokens=resp.output_tokens,
        cached_tokens=resp.cached_input_tokens,
        cost_usd=resp.cost_usd,
        latency_ms=round(total_latency_ms, 2),
        retrieval_hits=retrieval_hits,
        request_id=request_id,
    )
