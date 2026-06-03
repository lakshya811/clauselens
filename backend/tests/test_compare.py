"""Tests for contract version comparison — schema, comparator logic, and route.

Strategy:
  - Schema: verify ChangeType enum values, ChangedClause/CompareResult Pydantic
    models accept and reject expected data.
  - Comparator: mock complete_json, verify count recomputation, fallback on error,
    always uses strong model.
  - Route: TestClient with mocked LLM+settings, verify 200/404/503 status codes
    and response shape.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from app.llm.provider import LLMResponse
from app.schemas.compare import (
    ChangedClause,
    ChangeType,
    CompareRequest,
    CompareResult,
)
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


def test_change_type_enum_values() -> None:
    assert ChangeType.STRUCTURAL == "structural"
    assert ChangeType.SEMANTIC == "semantic"
    assert ChangeType.SURFACE == "surface"


def test_compare_result_minimal() -> None:
    r = CompareResult(summary="No significant changes.")
    assert r.changes == []
    assert r.structural_count == 0
    assert r.semantic_count == 0
    assert r.surface_count == 0


def test_compare_result_requires_summary() -> None:
    with pytest.raises(ValueError):
        CompareResult()  # missing required summary


def test_changed_clause_round_trip() -> None:
    c = ChangedClause(
        clause_reference="Section 8.2",
        change_type=ChangeType.STRUCTURAL,
        old_text="Licensor may terminate with 30 days notice.",
        new_text=None,
        explanation="Termination-for-convenience clause removed entirely.",
        risk_delta="Increases risk for Licensee — no exit right.",
    )
    assert c.change_type == ChangeType.STRUCTURAL
    assert c.new_text is None


def test_compare_request_requires_both_ids() -> None:
    with pytest.raises(ValueError):
        CompareRequest(doc_id_a="a")  # missing doc_id_b


# ---------------------------------------------------------------------------
# Comparator unit tests (mocked LLM)
# ---------------------------------------------------------------------------


def _llm_resp() -> LLMResponse:
    return LLMResponse(
        content="{}",
        model="gemini-2.5-flash",
        input_tokens=1200,
        output_tokens=300,
        cost_usd=0.00015,
        latency_ms=600.0,
    )


def _make_result() -> CompareResult:
    return CompareResult(
        changes=[
            ChangedClause(
                clause_reference="Section 4.1",
                change_type=ChangeType.SEMANTIC,
                old_text="reasonable efforts",
                new_text="best efforts",
                explanation="Stronger obligation on the vendor.",
            ),
            ChangedClause(
                clause_reference="Section 12",
                change_type=ChangeType.STRUCTURAL,
                old_text="Vendor may assign this agreement.",
                new_text=None,
                explanation="Assignment clause removed.",
            ),
            ChangedClause(
                clause_reference="Preamble",
                change_type=ChangeType.SURFACE,
                old_text="This Agreement (the 'Agreement')",
                new_text="This Agreement (this 'Agreement')",
                explanation="Typographic correction only.",
            ),
        ],
        structural_count=99,  # intentionally wrong — comparator must recompute
        semantic_count=99,
        surface_count=99,
        summary="Three changes between versions.",
        favours="Client",
    )


def test_comparator_returns_result() -> None:
    from app.analysis.comparator import compare_contracts

    expected = _make_result()
    llm = MagicMock()
    llm.complete_json.return_value = (expected, _llm_resp())

    result, obs = compare_contracts(
        "text a", "text b", "doc_a", "doc_b", llm, "cheap", "strong"
    )
    assert len(result.changes) == 3
    assert obs["input_tokens"] == 1200


def test_comparator_recomputes_counts() -> None:
    from app.analysis.comparator import compare_contracts

    llm = MagicMock()
    llm.complete_json.return_value = (_make_result(), _llm_resp())

    result, _ = compare_contracts(
        "a", "b", "doc_a", "doc_b", llm, "cheap", "strong"
    )
    # counts must match actual changes, not the model's (wrong) values
    assert result.structural_count == 1
    assert result.semantic_count == 1
    assert result.surface_count == 1


def test_comparator_fallback_on_error() -> None:
    from app.analysis.comparator import compare_contracts

    llm = MagicMock()
    llm.complete_json.side_effect = RuntimeError("timeout")

    result, obs = compare_contracts(
        "a", "b", "doc_a", "doc_b", llm, "cheap", "strong"
    )
    assert result.changes == []
    assert "failed" in result.summary.lower()
    assert obs["input_tokens"] == 0


def test_comparator_uses_strong_model() -> None:
    from app.analysis.comparator import compare_contracts

    llm = MagicMock()
    llm.complete_json.return_value = (
        CompareResult(summary="ok"),
        _llm_resp(),
    )

    _, obs = compare_contracts(
        "a", "b", "doc_a", "doc_b", llm, "cheap-model", "strong-model"
    )
    call_kwargs = llm.complete_json.call_args
    assert call_kwargs.kwargs["model"] == "strong-model"
    assert obs["model"] == "strong-model"


# ---------------------------------------------------------------------------
# Route tests
# ---------------------------------------------------------------------------


def _settings_mock() -> MagicMock:
    s = MagicMock()
    s.has_llm_credentials = True
    s.model_cheap = "gemini-2.5-flash-lite"
    s.model_strong = "gemini-2.5-flash"
    s.google_api_key = "fake"
    return s


def _fake_parsed(text: str = "Contract text.") -> MagicMock:
    m = MagicMock()
    m.full_text = text
    return m


@pytest.fixture()
def compare_client():
    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        c.app.state.documents = {
            "doc_v1": {
                "chunks": [],
                "filename": "v1.pdf",
                "parsed": _fake_parsed("Version A text."),
            },
            "doc_v2": {
                "chunks": [],
                "filename": "v2.pdf",
                "parsed": _fake_parsed("Version B text."),
            },
        }
        yield c


def test_compare_returns_200(compare_client: TestClient) -> None:
    expected = _make_result()
    expected.structural_count = 1
    expected.semantic_count = 1
    expected.surface_count = 1

    with (
        patch("app.routes.compare.get_settings", return_value=_settings_mock()),
        patch("app.routes.compare.get_llm") as mock_llm_factory,
    ):
        llm = MagicMock()
        llm.complete_json.return_value = (expected, _llm_resp())
        mock_llm_factory.return_value = llm

        r = compare_client.post(
            "/compare",
            json={"doc_id_a": "doc_v1", "doc_id_b": "doc_v2"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["doc_id_a"] == "doc_v1"
    assert body["doc_id_b"] == "doc_v2"
    assert body["result"]["summary"] == "Three changes between versions."
    assert body["request_id"] != ""


def test_compare_404_missing_doc_a(compare_client: TestClient) -> None:
    with patch("app.routes.compare.get_settings", return_value=_settings_mock()):
        r = compare_client.post(
            "/compare",
            json={"doc_id_a": "nonexistent", "doc_id_b": "doc_v2"},
        )
    assert r.status_code == 404


def test_compare_404_missing_doc_b(compare_client: TestClient) -> None:
    with patch("app.routes.compare.get_settings", return_value=_settings_mock()):
        r = compare_client.post(
            "/compare",
            json={"doc_id_a": "doc_v1", "doc_id_b": "nonexistent"},
        )
    assert r.status_code == 404


def test_compare_503_no_credentials(compare_client: TestClient) -> None:
    s = _settings_mock()
    s.has_llm_credentials = False
    with patch("app.routes.compare.get_settings", return_value=s):
        r = compare_client.post(
            "/compare",
            json={"doc_id_a": "doc_v1", "doc_id_b": "doc_v2"},
        )
    assert r.status_code == 503


def test_compare_response_has_change_counts(compare_client: TestClient) -> None:
    result = CompareResult(
        changes=[
            ChangedClause(
                clause_reference="§1",
                change_type=ChangeType.STRUCTURAL,
                explanation="Clause removed.",
            ),
            ChangedClause(
                clause_reference="§2",
                change_type=ChangeType.SURFACE,
                explanation="Typo fixed.",
            ),
        ],
        summary="Two changes.",
    )

    with (
        patch("app.routes.compare.get_settings", return_value=_settings_mock()),
        patch("app.routes.compare.get_llm") as mock_llm_factory,
    ):
        llm = MagicMock()
        llm.complete_json.return_value = (result, _llm_resp())
        mock_llm_factory.return_value = llm

        r = compare_client.post(
            "/compare",
            json={"doc_id_a": "doc_v1", "doc_id_b": "doc_v2"},
        )

    body = r.json()
    assert body["result"]["structural_count"] == 1
    assert body["result"]["surface_count"] == 1
    assert body["result"]["semantic_count"] == 0


def test_compare_response_has_token_fields(compare_client: TestClient) -> None:
    with (
        patch("app.routes.compare.get_settings", return_value=_settings_mock()),
        patch("app.routes.compare.get_llm") as mock_llm_factory,
    ):
        llm = MagicMock()
        llm.complete_json.return_value = (
            CompareResult(summary="ok"),
            _llm_resp(),
        )
        mock_llm_factory.return_value = llm

        r = compare_client.post(
            "/compare",
            json={"doc_id_a": "doc_v1", "doc_id_b": "doc_v2"},
        )

    body = r.json()
    assert body["input_tokens"] == 1200
    assert body["output_tokens"] == 300
    assert "cost_usd" in body
    assert "latency_ms" in body
