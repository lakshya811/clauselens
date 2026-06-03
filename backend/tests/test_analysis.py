"""Tests for clause extraction, risk flagging, and the /analyze route.

Strategy:
  - Schema validation: verify Pydantic models accept / reject expected data.
  - Extractor / flagger: mock complete_json to return controlled payloads,
    verify the functions parse them correctly and handle failures gracefully.
  - Route: TestClient with mocked LLM, verify status codes and response shape.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.llm.provider import LLMResponse
from app.schemas.analysis import (
    ClauseBundle,
    Party,
    PaymentTerms,
    RiskFlag,
    RiskReport,
    RiskSeverity,
)
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_clause_bundle_minimal_is_valid() -> None:
    b = ClauseBundle()
    assert b.parties == []
    assert b.payment.amount is None


def test_clause_bundle_with_data() -> None:
    b = ClauseBundle(
        parties=[Party(name="Acme Corp", role="Licensor")],
        effective_date="2024-01-01",
        governing_law="New York",
        payment=PaymentTerms(amount="$5,000/month", currency="USD"),
    )
    assert b.parties[0].name == "Acme Corp"
    assert b.payment.amount == "$5,000/month"


def test_risk_severity_enum_values() -> None:
    assert RiskSeverity.HIGH == "high"
    assert RiskSeverity.MEDIUM == "medium"
    assert RiskSeverity.LOW == "low"


def test_risk_report_requires_overall_risk_and_summary() -> None:
    with pytest.raises(ValueError):
        RiskReport()  # missing required fields


def test_risk_flag_round_trip() -> None:
    flag = RiskFlag(
        title="Uncapped liability",
        severity=RiskSeverity.HIGH,
        clause_reference="Section 8.2",
        explanation="No cap on direct damages.",
        recommendation="Negotiate a liability cap of 12 months of fees.",
    )
    assert flag.severity == RiskSeverity.HIGH
    assert "12 months" in flag.recommendation


def test_risk_report_default_flags_empty() -> None:
    r = RiskReport(overall_risk=RiskSeverity.LOW, summary="Looks clean.")
    assert r.flags == []


# ---------------------------------------------------------------------------
# Extractor tests (mocked LLM)
# ---------------------------------------------------------------------------


def _make_llm_resp(content: str = "{}") -> LLMResponse:
    return LLMResponse(
        content=content,
        model="gemini-2.5-flash-lite",
        input_tokens=600,
        output_tokens=120,
        cost_usd=0.00007,
        latency_ms=280.0,
    )


def _mock_llm(bundle: ClauseBundle) -> MagicMock:
    llm = MagicMock()
    llm.complete_json.return_value = (bundle, _make_llm_resp())
    return llm


def test_extract_clauses_returns_bundle() -> None:
    from app.analysis.extractor import extract_clauses

    expected = ClauseBundle(
        parties=[Party(name="Beta LLC", role="Licensee")],
        governing_law="California",
    )
    llm = _mock_llm(expected)
    bundle, obs = extract_clauses("contract text", "doc_x", llm, "flash-lite", "flash")
    assert bundle.governing_law == "California"
    assert obs["input_tokens"] == 600


def test_extract_clauses_fallback_on_error() -> None:
    from app.analysis.extractor import extract_clauses

    llm = MagicMock()
    llm.complete_json.side_effect = ValueError("bad JSON")
    bundle, obs = extract_clauses("text", "doc_x", llm, "flash-lite", "flash")
    assert "Extraction failed" in (bundle.confidence_note or "")
    assert obs["input_tokens"] == 0


def test_extract_uses_cheap_model() -> None:
    from app.analysis.extractor import extract_clauses

    llm = _mock_llm(ClauseBundle())
    _, obs = extract_clauses("text", "doc_x", llm, "cheap-model", "strong-model")
    call_kwargs = llm.complete_json.call_args
    assert call_kwargs.kwargs["model"] == "cheap-model"


# ---------------------------------------------------------------------------
# Risk flagger tests (mocked LLM)
# ---------------------------------------------------------------------------


def _mock_risk_llm(report: RiskReport) -> MagicMock:
    llm = MagicMock()
    llm.complete_json.return_value = (report, _make_llm_resp())
    return llm


def test_flag_risks_returns_report() -> None:
    from app.analysis.risk_flagger import flag_risks

    expected = RiskReport(
        flags=[
            RiskFlag(
                title="Uncapped liability",
                severity=RiskSeverity.HIGH,
                clause_reference="§8",
                explanation="No cap.",
                recommendation="Add a cap.",
            )
        ],
        overall_risk=RiskSeverity.HIGH,
        summary="High risk.",
    )
    llm = _mock_risk_llm(expected)
    report, obs = flag_risks("contract text", "doc_x", llm, "cheap", "strong")
    assert len(report.flags) == 1
    assert report.overall_risk == RiskSeverity.HIGH
    assert obs["output_tokens"] == 120


def test_flag_risks_fallback_on_error() -> None:
    from app.analysis.risk_flagger import flag_risks

    llm = MagicMock()
    llm.complete_json.side_effect = RuntimeError("timeout")
    report, _ = flag_risks("text", "doc_x", llm, "c", "s")
    assert report.overall_risk == RiskSeverity.HIGH
    assert "failed" in report.summary.lower()


def test_flag_risks_uses_strong_model() -> None:
    from app.analysis.risk_flagger import flag_risks

    llm = _mock_risk_llm(
        RiskReport(overall_risk=RiskSeverity.LOW, summary="ok")
    )
    _, obs = flag_risks("text", "doc_x", llm, "cheap-model", "strong-model")
    call_kwargs = llm.complete_json.call_args
    assert call_kwargs.kwargs["model"] == "strong-model"


# ---------------------------------------------------------------------------
# /analyze route tests
# ---------------------------------------------------------------------------


def _settings_mock() -> MagicMock:
    s = MagicMock()
    s.has_llm_credentials = True
    s.model_cheap = "gemini-2.5-flash-lite"
    s.model_strong = "gemini-2.5-flash"
    s.google_api_key = "fake"
    return s


def _fake_parsed(text: str = "Contract text here.") -> MagicMock:
    m = MagicMock()
    m.full_text = text
    m.page_count = 5
    m.ocr_page_count = 0
    return m


@pytest.fixture()
def analyze_client():
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.documents = {
            "doc_analyze01": {
                "chunks": [],
                "filename": "test.pdf",
                "parsed": _fake_parsed(),
            }
        }
        yield c


def test_analyze_returns_200(analyze_client: TestClient) -> None:
    bundle = ClauseBundle(governing_law="Delaware")
    report = RiskReport(overall_risk=RiskSeverity.LOW, summary="Low risk.")

    with (
        patch("app.routes.analyze.get_settings", return_value=_settings_mock()),
        patch("app.routes.analyze.get_llm") as mock_llm_factory,
    ):
        llm = MagicMock()
        llm.complete_json.side_effect = [
            (bundle, _make_llm_resp()),
            (report, _make_llm_resp()),
        ]
        mock_llm_factory.return_value = llm

        r = analyze_client.post("/analyze/doc_analyze01")

    assert r.status_code == 200
    body = r.json()
    assert body["doc_id"] == "doc_analyze01"
    assert body["clauses"]["governing_law"] == "Delaware"
    assert body["risks"]["overall_risk"] == "low"
    assert body["request_id"] != ""


def test_analyze_unknown_doc_returns_404(analyze_client: TestClient) -> None:
    with patch("app.routes.analyze.get_settings", return_value=_settings_mock()):
        r = analyze_client.post("/analyze/doc_notfound")
    assert r.status_code == 404


def test_analyze_no_credentials_returns_503(analyze_client: TestClient) -> None:
    s = _settings_mock()
    s.has_llm_credentials = False
    with patch("app.routes.analyze.get_settings", return_value=s):
        r = analyze_client.post("/analyze/doc_analyze01")
    assert r.status_code == 503


def test_analyze_response_has_token_counts(analyze_client: TestClient) -> None:
    bundle = ClauseBundle()
    report = RiskReport(overall_risk=RiskSeverity.MEDIUM, summary="Medium risk.")

    with (
        patch("app.routes.analyze.get_settings", return_value=_settings_mock()),
        patch("app.routes.analyze.get_llm") as mock_llm_factory,
    ):
        llm = MagicMock()
        llm.complete_json.side_effect = [
            (bundle, _make_llm_resp()),
            (report, _make_llm_resp()),
        ]
        mock_llm_factory.return_value = llm
        r = analyze_client.post("/analyze/doc_analyze01")

    body = r.json()
    assert body["input_tokens"] == 1200  # 600 + 600
    assert body["output_tokens"] == 240  # 120 + 120
