"""Smoke test for the app scaffold — proves the API boots and config loads.

Runs without any LLM key or heavy ML deps, so CI stays fast and green from day 1.
"""

from __future__ import annotations

from app.main import create_app
from fastapi.testclient import TestClient


def test_health_ok() -> None:
    client = TestClient(create_app())
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert body["vector_backend"] in {"faiss", "pgvector"}
