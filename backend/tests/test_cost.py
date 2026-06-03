"""Tests for cost accounting — pure arithmetic, no API calls."""

from __future__ import annotations

import pytest
from app.llm.cost import PRICING_TABLE, calculate_cost, routing_savings_pct


def test_zero_tokens_is_zero_cost() -> None:
    assert calculate_cost("gemini-2.5-flash", 0, 0) == 0.0


def test_cost_is_positive() -> None:
    cost = calculate_cost("gemini-2.5-flash", 1000, 200)
    assert cost > 0.0


def test_flash_lite_cheaper_than_flash() -> None:
    flash = calculate_cost("gemini-2.5-flash", 2000, 500)
    lite = calculate_cost("gemini-2.5-flash-lite", 2000, 500)
    assert lite < flash


def test_cached_tokens_cheaper_than_standard() -> None:
    # All tokens cached vs none cached.
    full_price = calculate_cost("gemini-2.5-flash", input_tokens=1000, output_tokens=0)
    cached_price = calculate_cost(
        "gemini-2.5-flash", input_tokens=1000, output_tokens=0, cached_input_tokens=1000
    )
    assert cached_price < full_price


def test_unknown_model_falls_back_to_default() -> None:
    cost = calculate_cost("unknown-model-xyz", 1000, 200)
    default_cost = calculate_cost("_default", 1000, 200)
    assert cost == default_cost


def test_routing_savings_all_cheap() -> None:
    # If all calls go to cheap model, savings should be positive.
    pct = routing_savings_pct("gemini-2.5-flash-lite", "gemini-2.5-flash", 100, 0)
    assert pct > 0.0


def test_routing_savings_all_strong_is_zero() -> None:
    # No routing → 0% savings.
    pct = routing_savings_pct("gemini-2.5-flash-lite", "gemini-2.5-flash", 0, 100)
    assert pct == 0.0


def test_routing_savings_mixed_is_between() -> None:
    pct = routing_savings_pct("gemini-2.5-flash-lite", "gemini-2.5-flash", 50, 50)
    assert 0.0 < pct < 100.0


def test_all_models_in_pricing_table_have_positive_rates() -> None:
    for name, p in PRICING_TABLE.items():
        assert p.input_per_mtok >= 0, f"{name}: negative input rate"
        assert p.output_per_mtok > 0, f"{name}: zero/negative output rate"


def test_cost_scales_linearly() -> None:
    c1 = calculate_cost("gemini-2.5-flash", 1000, 0)
    c2 = calculate_cost("gemini-2.5-flash", 2000, 0)
    assert pytest.approx(c2, rel=1e-6) == c1 * 2
