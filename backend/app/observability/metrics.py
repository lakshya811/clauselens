"""Aggregate metrics computed from the JSONL request log.

Interview answer:
  "/metrics reads the last 500 log lines (O(log-size), not a DB query) and
  computes per-model aggregates in Python. For a portfolio demo that handles
  tens of queries this is instant. I'd add a time-series DB (InfluxDB, TimescaleDB)
  once query volume grows, but the interface — a JSON object with per-model
  latency percentiles and cost totals — stays identical."
"""

from __future__ import annotations

import statistics
from typing import Any

from app.observability.logger import read_recent


def _percentile(data: list[float], p: int) -> float:
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = max(0, int(len(sorted_data) * p / 100) - 1)
    return round(sorted_data[idx], 2)


def compute_metrics(window: int = 500) -> dict[str, Any]:
    """Return aggregate metrics over the last `window` requests."""
    records = read_recent(window)

    total_requests = len(records)
    total_errors = sum(1 for r in records if r.get("error"))
    total_cost_usd = round(sum(r.get("cost_usd", 0.0) for r in records), 6)
    total_input_tokens = sum(r.get("input_tokens", 0) for r in records)
    total_output_tokens = sum(r.get("output_tokens", 0) for r in records)
    total_cached_tokens = sum(r.get("cached_tokens", 0) for r in records)

    # Per-model breakdown
    by_model: dict[str, dict[str, Any]] = {}
    for rec in records:
        model = rec.get("model", "unknown")
        if model not in by_model:
            by_model[model] = {
                "requests": 0,
                "latencies_ms": [],
                "cost_usd": 0.0,
                "input_tokens": 0,
                "output_tokens": 0,
            }
        m = by_model[model]
        m["requests"] += 1
        lat = rec.get("latency_ms", 0.0)
        if lat > 0:
            m["latencies_ms"].append(lat)
        m["cost_usd"] += rec.get("cost_usd", 0.0)
        m["input_tokens"] += rec.get("input_tokens", 0)
        m["output_tokens"] += rec.get("output_tokens", 0)

    model_stats: dict[str, Any] = {}
    for model, m in by_model.items():
        lats = m["latencies_ms"]
        model_stats[model] = {
            "requests": m["requests"],
            "latency_p50_ms": _percentile(lats, 50),
            "latency_p95_ms": _percentile(lats, 95),
            "latency_mean_ms": round(statistics.mean(lats), 2) if lats else 0.0,
            "cost_usd": round(m["cost_usd"], 6),
            "input_tokens": m["input_tokens"],
            "output_tokens": m["output_tokens"],
        }

    cost_per_query = (
        round(total_cost_usd / total_requests, 8) if total_requests else 0.0
    )

    all_latencies = [
        r.get("latency_ms", 0.0) for r in records if r.get("latency_ms", 0.0) > 0
    ]

    return {
        "window_size": window,
        "total_requests": total_requests,
        "total_errors": total_errors,
        "error_rate": round(total_errors / total_requests, 4) if total_requests else 0.0,
        "total_cost_usd": total_cost_usd,
        "cost_per_query_usd": cost_per_query,
        "total_input_tokens": total_input_tokens,
        "total_output_tokens": total_output_tokens,
        "total_cached_tokens": total_cached_tokens,
        "latency_p50_ms": _percentile(all_latencies, 50),
        "latency_p95_ms": _percentile(all_latencies, 95),
        "by_model": model_stats,
    }
