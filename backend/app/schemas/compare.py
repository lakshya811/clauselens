"""Pydantic models for contract version comparison.

These are used as Gemini response_schema (JSON mode) and as API response
models. Each change is classified at three levels of severity:
  Structural  — a clause was added, removed, or substantially rewritten
  Semantic    — meaning changed but clause is still present (e.g. narrower scope,
                new obligation, changed party)
  Surface     — wording/punctuation/formatting only, no legal effect

The distinction matters: a recruiter demo that says "37 changes (5 Structural,
12 Semantic, 20 Surface)" is far more useful than a raw diff.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class ChangeType(str, Enum):
    STRUCTURAL = "structural"
    SEMANTIC = "semantic"
    SURFACE = "surface"


class ChangedClause(BaseModel):
    clause_reference: str = Field(
        ..., description="Clause or section identifier, e.g. 'Section 4.2'."
    )
    change_type: ChangeType
    old_text: str | None = Field(None, description="Relevant excerpt from version A.")
    new_text: str | None = Field(None, description="Relevant excerpt from version B.")
    explanation: str = Field(
        ..., description="Why this change matters legally and which party it favours."
    )
    risk_delta: str | None = Field(
        None,
        description="Increase/decrease in risk exposure, if material.",
    )


class CompareResult(BaseModel):
    """LLM-produced structured diff between two contract versions."""

    changes: list[ChangedClause] = Field(default_factory=list)
    structural_count: int = Field(0, description="Number of structural changes.")
    semantic_count: int = Field(0, description="Number of semantic changes.")
    surface_count: int = Field(0, description="Number of surface-level changes.")
    summary: str = Field(
        ...,
        description="2-3 sentence executive summary of the most significant changes.",
    )
    favours: str | None = Field(
        None,
        description="Which party benefits overall from version B vs A, and why.",
    )


class CompareRequest(BaseModel):
    doc_id_a: str = Field(..., description="doc_id of the first (older) version.")
    doc_id_b: str = Field(..., description="doc_id of the second (newer) version.")


class CompareResponse(BaseModel):
    doc_id_a: str
    doc_id_b: str
    result: CompareResult
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: float
    request_id: str
