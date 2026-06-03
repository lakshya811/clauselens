"""Tests for the Q&A route and observability layer.

Strategy:
  - Metrics: pure-logic tests on compute_metrics() using a temp log file.
  - Q&A route: full FastAPI TestClient with the LLM patched to avoid API calls.
    The vector store is left as the real FAISSVectorStore (empty index → 0 hits),
    which exercises the BM25-only fallback path cleanly.
"""

from __future__ import annotations

import json
import tempfile
import time
from typing import Any
from unittest.mock import MagicMock, patch

import app.observability.logger as obs_logger
import pytest
from app.llm.provider import LLMResponse
from app.observability.metrics import compute_metrics
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_log(records: list[dict[str, Any]], path: str) -> None:
    with open(path, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")


def _make_record(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "ts": time.time(),
        "request_id": "abc123",
        "route": "/ask",
        "model": "gemini-2.5-flash",
        "routing_reason": "task_complex_qa_strong",
        "input_tokens": 1000,
        "output_tokens": 200,
        "cached_tokens": 0,
        "cost_usd": 0.0008,
        "latency_ms": 450.0,
        "retrieval_hits": 4,
        "doc_id": "doc_abc",
        "error": "",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Observability / metrics tests
# ---------------------------------------------------------------------------


class TestMetrics:
    def setup_method(self) -> None:
        self._tmpdir = tempfile.mkdtemp()
        obs_logger._log_file = None  # reset between tests

    def _init(self) -> None:
        obs_logger.init_logger(self._tmpdir)

    def test_empty_log_returns_zero_totals(self) -> None:
        self._init()
        m = compute_metrics()
        assert m["total_requests"] == 0
        assert m["total_cost_usd"] == 0.0
        assert m["cost_per_query_usd"] == 0.0

    def test_single_record_totals(self) -> None:
        self._init()
        obs_logger.log_request(
            route="/ask", model="gemini-2.5-flash",
            input_tokens=500, output_tokens=100, cost_usd=0.001,
            latency_ms=300.0,
        )
        m = compute_metrics()
        assert m["total_requests"] == 1
        assert m["total_input_tokens"] == 500
        assert m["total_output_tokens"] == 100
        assert m["total_cost_usd"] == pytest.approx(0.001, rel=1e-6)

    def test_cost_per_query(self) -> None:
        self._init()
        obs_logger.log_request(route="/ask", model="m", cost_usd=0.002, latency_ms=100.0)
        obs_logger.log_request(route="/ask", model="m", cost_usd=0.004, latency_ms=100.0)
        m = compute_metrics()
        assert m["cost_per_query_usd"] == pytest.approx(0.003, rel=1e-6)

    def test_error_rate(self) -> None:
        self._init()
        obs_logger.log_request(route="/ask", model="m", latency_ms=100.0)
        obs_logger.log_request(route="/ask", model="m", latency_ms=100.0, error="timeout")
        m = compute_metrics()
        assert m["total_errors"] == 1
        assert m["error_rate"] == pytest.approx(0.5, rel=1e-6)

    def test_per_model_breakdown(self) -> None:
        self._init()
        obs_logger.log_request(route="/ask", model="flash", cost_usd=0.001, latency_ms=200.0)
        obs_logger.log_request(route="/ask", model="flash-lite", cost_usd=0.0001, latency_ms=100.0)
        m = compute_metrics()
        assert "flash" in m["by_model"]
        assert "flash-lite" in m["by_model"]

    def test_latency_percentiles_populated(self) -> None:
        self._init()
        for lat in [100.0, 200.0, 300.0, 400.0, 500.0]:
            obs_logger.log_request(route="/ask", model="m", latency_ms=lat)
        m = compute_metrics()
        assert m["latency_p50_ms"] > 0
        assert m["latency_p95_ms"] >= m["latency_p50_ms"]

    def test_window_limits_records(self) -> None:
        self._init()
        for _ in range(20):
            obs_logger.log_request(route="/ask", model="m", latency_ms=50.0)
        m = compute_metrics(window=5)
        assert m["total_requests"] == 5


# ---------------------------------------------------------------------------
# Q&A route tests (mocked LLM)
# ---------------------------------------------------------------------------


def _mock_llm_response(answer: str = "The payment is $1,000 per month.") -> LLMResponse:
    return LLMResponse(
        content=answer,
        model="gemini-2.5-flash-lite",
        input_tokens=800,
        output_tokens=80,
        cost_usd=0.000041,
        latency_ms=320.0,
        cached_input_tokens=0,
    )


@pytest.fixture()
def client_with_doc():
    """TestClient with a fake document pre-loaded in app state."""
    from app.ingestion.chunker import Chunk
    from app.main import create_app
    from app.rag.store import FAISSVectorStore

    app = create_app()

    # Pre-load a fake document so the route doesn't 404
    fake_chunks = [
        Chunk(
            text="The Licensee shall pay $1,000 per month on the first business day.",
            doc_id="doc_test001",
            chunk_index=0,
            clause_heading="Section 4. Payment Terms",
            page_start=3,
            page_end=3,
        ),
        Chunk(
            text="Either party may terminate with thirty (30) days written notice.",
            doc_id="doc_test001",
            chunk_index=1,
            clause_heading="Section 9. Termination",
            page_start=7,
            page_end=7,
        ),
    ]
    with tempfile.TemporaryDirectory() as tmpdir:
        vs = FAISSVectorStore(index_dir=tmpdir)

        with TestClient(app) as c:
            c.app.state.documents = {
                "doc_test001": {
                    "chunks": fake_chunks,
                    "filename": "test_contract.pdf",
                    "parsed": MagicMock(page_count=10, ocr_page_count=0),
                }
            }
            c.app.state.vector_store = vs
            yield c


def _settings_with_key() -> MagicMock:
    s = MagicMock()
    s.has_llm_credentials = True
    s.model_cheap = "gemini-2.5-flash-lite"
    s.model_strong = "gemini-2.5-flash"
    s.retrieval_top_k = 4
    s.rerank_top_n = 2
    s.google_api_key = "fake-key"
    return s


def test_ask_returns_200_with_mocked_llm(client_with_doc: TestClient) -> None:
    mock_resp = _mock_llm_response()
    with (
        patch("app.routes.qa.get_llm") as mock_get_llm,
        patch("app.routes.qa.embed_query", return_value=[0.1] * 768),
        patch("app.routes.qa.get_settings", return_value=_settings_with_key()),
    ):
        llm = MagicMock()
        llm.timed_complete.return_value = mock_resp
        mock_get_llm.return_value = llm

        r = client_with_doc.post(
            "/ask",
            json={"doc_id": "doc_test001", "question": "What is the payment amount?"},
        )
    assert r.status_code == 200
    body = r.json()
    assert "answer" in body
    assert body["answer"] == mock_resp.content
    assert "citations" in body
    assert body["model"] == "gemini-2.5-flash-lite"
    assert body["input_tokens"] == 800
    assert body["retrieval_hits"] >= 0


def test_ask_unknown_doc_returns_404(client_with_doc: TestClient) -> None:
    with patch("app.routes.qa.get_settings", return_value=_settings_with_key()):
        r = client_with_doc.post(
            "/ask",
            json={"doc_id": "doc_doesnotexist", "question": "Anything?"},
        )
    assert r.status_code == 404


def test_ask_no_credentials_returns_503() -> None:
    from app.main import create_app

    app = create_app()
    with patch("app.routes.qa.get_settings") as mock_settings:
        s = MagicMock()
        s.has_llm_credentials = False
        mock_settings.return_value = s
        with TestClient(app) as c:
            r = c.post(
                "/ask",
                json={"doc_id": "doc_x", "question": "test?"},
            )
    assert r.status_code == 503


def test_ask_question_too_short_returns_422(client_with_doc: TestClient) -> None:
    r = client_with_doc.post(
        "/ask",
        json={"doc_id": "doc_test001", "question": "hi"},
    )
    assert r.status_code == 422


def test_metrics_endpoint_returns_dict(client_with_doc: TestClient) -> None:
    r = client_with_doc.get("/metrics")
    assert r.status_code == 200
    body = r.json()
    assert "total_requests" in body
    assert "total_cost_usd" in body
    assert "by_model" in body


def test_ask_response_has_request_id(client_with_doc: TestClient) -> None:
    mock_resp = _mock_llm_response()
    with (
        patch("app.routes.qa.get_llm") as mock_get_llm,
        patch("app.routes.qa.embed_query", return_value=[0.1] * 768),
        patch("app.routes.qa.get_settings", return_value=_settings_with_key()),
    ):
        llm = MagicMock()
        llm.timed_complete.return_value = mock_resp
        mock_get_llm.return_value = llm

        r = client_with_doc.post(
            "/ask",
            json={"doc_id": "doc_test001", "question": "When does the contract expire?"},
        )
    assert r.status_code == 200
    assert r.json()["request_id"] != ""
