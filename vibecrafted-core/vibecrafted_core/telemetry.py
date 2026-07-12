"""Provider-neutral model usage and cost estimation contracts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    input_per_million: float
    cached_input_per_million: float
    output_per_million: float
    source: str


# API-equivalent rates. Provider-reported CLI cost always wins; these rates are
# only a transparent fallback when a stream exposes tokens but no monetary cost.
_PRICES: tuple[tuple[tuple[str, ...], ModelPrice], ...] = (
    (("grok-build", "grok-code-fast"), ModelPrice(1.0, 0.2, 2.0, "xai-api-2026-07")),
    (("gpt-5.6-sol",), ModelPrice(5.0, 0.5, 30.0, "openai-api-2026-07")),
    (("gpt-5.6-terra",), ModelPrice(2.5, 0.25, 15.0, "openai-api-2026-07")),
    (("gpt-5.6-luna",), ModelPrice(1.0, 0.1, 6.0, "openai-api-2026-07")),
    (("gpt-5.5",), ModelPrice(5.0, 0.5, 30.0, "openai-api-2026-07")),
    (("gpt-5.4",), ModelPrice(2.5, 0.25, 15.0, "openai-api-2026-07")),
    (("gpt-5",), ModelPrice(1.25, 0.125, 10.0, "openai-api-2026-07")),
)


def model_price(model: str) -> ModelPrice | None:
    normalized = (model or "").strip().lower()
    for aliases, price in _PRICES:
        if any(alias in normalized for alias in aliases):
            return price
    return None


def estimate_cost_usd(
    model: str,
    *,
    tokens_input: int,
    tokens_cached_input: int,
    tokens_output: int,
) -> tuple[float | None, str | None]:
    price = model_price(model)
    if price is None or not (tokens_input or tokens_cached_input or tokens_output):
        return None, None
    cost = (
        tokens_input * price.input_per_million
        + tokens_cached_input * price.cached_input_per_million
        + tokens_output * price.output_per_million
    ) / 1_000_000
    return round(cost, 6), f"estimated:{price.source}"
