"""Pydantic models for the Q&A (chat) route."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CitedChunk(BaseModel):
    chunk_index: int
    citation: str = Field(..., description="Human-readable clause + page label.")
    text_snippet: str = Field(..., description="First 200 chars of the chunk text.")
    score: float = Field(..., description="Retrieval relevance score (higher = more relevant).")


class AskRequest(BaseModel):
    doc_id: str = Field(..., description="Document ID from the upload response.")
    question: str = Field(..., min_length=3, max_length=2000)
    top_k: int | None = Field(None, ge=1, le=20, description="Override retrieval top-k.")


class AskResponse(BaseModel):
    answer: str
    citations: list[CitedChunk]
    model: str
    routing_reason: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: float
    retrieval_hits: int
    request_id: str
