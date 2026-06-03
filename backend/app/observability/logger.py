"""Request-level observability — JSONL append-only log.

Every LLM call writes one JSON line:
  {ts, request_id, route, model, routing_reason,
   input_tokens, output_tokens, cached_tokens, cost_usd,
   latency_ms, retrieval_hits, doc_id, error}

Interview answer:
  "Each log line is structured JSON so it can be ingested by any log aggregator
  (Loki, CloudWatch, Datadog) without parsing. I append to a rolling JSONL file
  locally and expose a /metrics endpoint that reads the last N lines and returns
  per-model aggregates — p50/p95 latency, total cost, token throughput. In prod
  I'd swap the file sink for an async queue (e.g. Pub/Sub) to avoid blocking the
  request thread, but for a portfolio demo the file write is <1ms and shows the
  full observability story."
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_log_file: Path | None = None


def init_logger(log_dir: str) -> None:
    global _log_file
    p = Path(log_dir)
    p.mkdir(parents=True, exist_ok=True)
    _log_file = p / "requests.jsonl"
    logger.info("Observability log: %s", _log_file)


def log_request(
    *,
    route: str,
    model: str,
    routing_reason: str = "",
    input_tokens: int = 0,
    output_tokens: int = 0,
    cached_tokens: int = 0,
    cost_usd: float = 0.0,
    latency_ms: float = 0.0,
    retrieval_hits: int = 0,
    doc_id: str = "",
    error: str = "",
    extra: dict[str, Any] | None = None,
) -> str:
    """Append one JSON line to the JSONL log. Returns the request_id."""
    request_id = uuid.uuid4().hex[:12]
    record: dict[str, Any] = {
        "ts": time.time(),
        "request_id": request_id,
        "route": route,
        "model": model,
        "routing_reason": routing_reason,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "cost_usd": cost_usd,
        "latency_ms": latency_ms,
        "retrieval_hits": retrieval_hits,
        "doc_id": doc_id,
        "error": error,
    }
    if extra:
        record.update(extra)

    if _log_file is not None:
        try:
            with open(_log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
        except OSError:
            logger.warning("Could not write to observability log: %s", _log_file)
    else:
        # Log to stderr until init_logger() is called (e.g. during tests).
        logger.debug("obs: %s", json.dumps(record))

    return request_id


def read_recent(n: int = 500) -> list[dict[str, Any]]:
    """Return up to n most-recent log records (newest last)."""
    if _log_file is None or not _log_file.exists():
        return []
    lines: list[str] = []
    try:
        with open(_log_file) as f:
            lines = f.readlines()
    except OSError:
        return []
    records: list[dict[str, Any]] = []
    for line in lines[-n:]:
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records
