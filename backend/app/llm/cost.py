"""Per-token cost accounting.

All prices are USD per 1 million tokens (MTok) from the Google AI Studio /
Gemini API pricing page, captured 2026-06.

Interview answer for "how do you track cost-per-query?":
  "I keep a pricing table keyed on model name. Every LLMResponse carries
  input_tokens, output_tokens, and cached_input_tokens. The cost function
  multiplies each by its tier rate and sums them. The observability middleware
  reads .cost_usd off every response and writes it to the JSONL log — no extra
  instrumentation needed at call sites."

Note: flash-lite has a free tier with 0 $/MTok for small quotas. We track cost
at published paid rates so the system is correct when scaled beyond free tier.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPricing:
    model: str
    input_per_mtok: float        # $ per million input tokens
    output_per_mtok: float       # $ per million output tokens
    cached_input_per_mtok: float = 0.0  # $ per million cached input tokens (prompt cache)


# Gemini pricing as of 2026-06 (prompts ≤ 200K tokens tier).
# Source: https://ai.google.dev/gemini-api/docs/pricing
PRICING_TABLE: dict[str, ModelPricing] = {
    "gemini-2.5-flash": ModelPricing(
        model="gemini-2.5-flash",
        input_per_mtok=0.30,
        output_per_mtok=2.50,
        cached_input_per_mtok=0.075,
    ),
    "gemini-2.5-flash-lite": ModelPricing(
        model="gemini-2.5-flash-lite",
        input_per_mtok=0.10,
        output_per_mtok=0.40,
        cached_input_per_mtok=0.025,
    ),
    # Fallback entry — used when a model name isn't explicitly listed.
    # Prices match flash so we never under-count.
    "_default": ModelPricing(
        model="_default",
        input_per_mtok=0.30,
        output_per_mtok=2.50,
        cached_input_per_mtok=0.075,
    ),
}


def calculate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cached_input_tokens: int = 0,
) -> float:
    """Return cost in USD for one LLM call.

    cached_input_tokens are billed at the cheaper cached rate; the remainder
    of input_tokens at the standard input rate.
    """
    pricing = PRICING_TABLE.get(model, PRICING_TABLE["_default"])
    standard_input = max(input_tokens - cached_input_tokens, 0)
    cost = (
        standard_input * pricing.input_per_mtok / 1_000_000
        + cached_input_tokens * pricing.cached_input_per_mtok / 1_000_000
        + output_tokens * pricing.output_per_mtok / 1_000_000
    )
    return round(cost, 8)


def routing_savings_pct(
    cheap_model: str,
    strong_model: str,
    cheap_calls: int,
    strong_calls: int,
    avg_input_tokens: int = 2000,
    avg_output_tokens: int = 500,
) -> float:
    """Estimate % cost saved by routing cheap_calls to the cheap model.

    Used in the README to produce a defensible 'routing saved X%' number.
    """
    cheap_p = PRICING_TABLE.get(cheap_model, PRICING_TABLE["_default"])
    strong_p = PRICING_TABLE.get(strong_model, PRICING_TABLE["_default"])

    total_calls = cheap_calls + strong_calls
    if total_calls == 0:
        return 0.0

    all_strong = total_calls * (
        avg_input_tokens * strong_p.input_per_mtok / 1_000_000
        + avg_output_tokens * strong_p.output_per_mtok / 1_000_000
    )
    mixed = (
        cheap_calls * (
            avg_input_tokens * cheap_p.input_per_mtok / 1_000_000
            + avg_output_tokens * cheap_p.output_per_mtok / 1_000_000
        )
        + strong_calls * (
            avg_input_tokens * strong_p.input_per_mtok / 1_000_000
            + avg_output_tokens * strong_p.output_per_mtok / 1_000_000
        )
    )
    if all_strong == 0:
        return 0.0
    return round((1 - mixed / all_strong) * 100, 1)
