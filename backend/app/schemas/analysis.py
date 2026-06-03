"""Pydantic models for clause extraction and risk flagging.

These are used both as Gemini response_schema (JSON mode) and as API response
models. Pydantic v2 + from __future__ import annotations means field types are
strings at class-definition time, which is safe for both uses.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Clause extraction
# ---------------------------------------------------------------------------


class Party(BaseModel):
    name: str = Field(..., description="Legal name of the party.")
    role: str = Field(..., description="Role in the contract, e.g. Licensor, Licensee, Vendor.")


class PaymentTerms(BaseModel):
    amount: str | None = Field(None, description="Payment amount or schedule.")
    due_date: str | None = Field(None, description="Due date or frequency.")
    late_penalty: str | None = Field(None, description="Late payment penalty clause, if any.")
    currency: str | None = Field(None, description="Currency, e.g. USD.")


class LiabilityTerms(BaseModel):
    cap: str | None = Field(None, description="Liability cap amount or formula.")
    exclusions: list[str] = Field(default_factory=list, description="Excluded liability cats.")
    indemnification: str | None = Field(None, description="Indemnification obligations summary.")


class TerminationTerms(BaseModel):
    notice_period: str | None = Field(None, description="Required notice period, e.g. '30 days'.")
    for_cause: str | None = Field(None, description="Termination for cause conditions.")
    for_convenience: str | None = Field(None, description="Termination for convenience conditions.")
    survival_clauses: list[str] = Field(default_factory=list, description="Surviving clauses.")


class ClauseBundle(BaseModel):
    """Structured extraction of the five key clause types."""

    parties: list[Party] = Field(default_factory=list)
    effective_date: str | None = Field(None, description="Contract effective date.")
    expiry_date: str | None = Field(None, description="Contract expiry or end date.")
    governing_law: str | None = Field(None, description="Governing law jurisdiction.")
    payment: PaymentTerms = Field(default_factory=PaymentTerms)
    liability: LiabilityTerms = Field(default_factory=LiabilityTerms)
    termination: TerminationTerms = Field(default_factory=TerminationTerms)
    confidence_note: str | None = Field(
        None,
        description="Any caveats about extraction confidence or missing information.",
    )


# ---------------------------------------------------------------------------
# Risk flagging
# ---------------------------------------------------------------------------


class RiskSeverity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RiskFlag(BaseModel):
    title: str = Field(..., description="Short title for the risk, e.g. 'Uncapped liability'.")
    severity: RiskSeverity
    clause_reference: str = Field(..., description="Clause or section where the risk appears.")
    explanation: str = Field(..., description="Why this is a risk and what to watch for.")
    recommendation: str = Field(..., description="Suggested mitigation or negotiation point.")


class RiskReport(BaseModel):
    flags: list[RiskFlag] = Field(default_factory=list)
    overall_risk: RiskSeverity = Field(
        ..., description="Overall contract risk level based on the flags."
    )
    summary: str = Field(..., description="2-3 sentence executive summary of the risk profile.")


# ---------------------------------------------------------------------------
# Combined analysis response (extraction + risk in one API response)
# ---------------------------------------------------------------------------


class AnalysisResponse(BaseModel):
    doc_id: str
    clauses: ClauseBundle
    risks: RiskReport
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    cost_usd: float
    latency_ms: float
    request_id: str
