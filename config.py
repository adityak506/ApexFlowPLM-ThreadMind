"""Configuration management and LLM pricing tables for ThreadMind PLM.

Provides:
- Configurable LLM pricing tables for calculating estimated query costs.
- Support for multiple LLM providers (Gemini, OpenAI, Claude, Local/Mock).
- Runtime configuration overrides via environment variables or API.
- Safe defaults preventing unmetered execution.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(frozen=True)
class ModelPrice:
    """Pricing rates in USD per one million tokens."""
    input_per_million: float
    output_per_million: float

    def calculate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Calculate total USD cost for a given input and output token count."""
        cost_in = (max(0, input_tokens) / 1_000_000.0) * self.input_per_million
        cost_out = (max(0, output_tokens) / 1_000_000.0) * self.output_per_million
        return round(cost_in + cost_out, 6)


# Configurable default price table (USD per 1,000,000 tokens)
# Source: Official vendor pricing tables as of 2025/2026 baselines
DEFAULT_MODEL_PRICING: dict[str, ModelPrice] = {
    # Google Gemini Models
    "gemini-1.5-pro": ModelPrice(input_per_million=3.50, output_per_million=10.50),
    "gemini-1.5-flash": ModelPrice(input_per_million=0.075, output_per_million=0.30),
    "gemini-2.0-flash": ModelPrice(input_per_million=0.10, output_per_million=0.40),
    "gemini-2.5-pro": ModelPrice(input_per_million=3.00, output_per_million=12.00),

    # OpenAI Models
    "gpt-4o": ModelPrice(input_per_million=2.50, output_per_million=10.00),
    "gpt-4o-mini": ModelPrice(input_per_million=0.15, output_per_million=0.60),
    "o1": ModelPrice(input_per_million=15.00, output_per_million=60.00),
    "o3-mini": ModelPrice(input_per_million=1.10, output_per_million=4.40),

    # Anthropic Models
    "claude-3-5-sonnet": ModelPrice(input_per_million=3.00, output_per_million=15.00),
    "claude-3-5-haiku": ModelPrice(input_per_million=0.80, output_per_million=4.00),

    # Mock & Local Engineering Agent Fallback
    "mock-llm": ModelPrice(input_per_million=0.50, output_per_million=1.50),
    "threadmind-agent": ModelPrice(input_per_million=0.50, output_per_million=1.50),
    "default": ModelPrice(input_per_million=0.50, output_per_million=1.50),
}

# Runtime price table that can be mutated dynamically in tests or via settings
_ACTIVE_PRICING_TABLE: dict[str, ModelPrice] = dict(DEFAULT_MODEL_PRICING)


def get_model_pricing(model_name: str | None) -> ModelPrice:
    """Retrieve pricing rates for a model, matching case-insensitively or falling back to defaults."""
    if not model_name:
        return _ACTIVE_PRICING_TABLE.get("default", ModelPrice(0.50, 1.50))

    clean_name = model_name.strip().lower()

    # Exact match
    if clean_name in _ACTIVE_PRICING_TABLE:
        return _ACTIVE_PRICING_TABLE[clean_name]

    # Partial / substring match (e.g. 'gpt-4o-2024-08-06' -> 'gpt-4o')
    for key, price in _ACTIVE_PRICING_TABLE.items():
        if key != "default" and key in clean_name:
            return price

    # Check environment variable overrides
    env_in = os.getenv("LLM_PRICE_INPUT_PER_M")
    env_out = os.getenv("LLM_PRICE_OUTPUT_PER_M")
    if env_in is not None and env_out is not None:
        try:
            return ModelPrice(float(env_in), float(env_out))
        except ValueError:
            pass

    return _ACTIVE_PRICING_TABLE.get("default", ModelPrice(0.50, 1.50))


def set_model_price(model_name: str, input_per_million: float, output_per_million: float) -> None:
    """Register or update a model price in the active pricing table."""
    _ACTIVE_PRICING_TABLE[model_name.strip().lower()] = ModelPrice(
        input_per_million=float(input_per_million),
        output_per_million=float(output_per_million),
    )


def reset_model_pricing() -> None:
    """Reset the active pricing table back to default values."""
    global _ACTIVE_PRICING_TABLE
    _ACTIVE_PRICING_TABLE = dict(DEFAULT_MODEL_PRICING)


def calculate_llm_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate the estimated USD cost for an LLM call given input and output token counts."""
    pricing = get_model_pricing(model_name)
    return pricing.calculate_cost(input_tokens, output_tokens)


def get_default_model_name() -> str:
    """Retrieve default LLM model name from env or fallback."""
    return os.getenv("LLM_MODEL_NAME", "mock-llm").strip().lower()


def get_max_agent_turns() -> int:
    """Retrieve max allowed turns in the agent loop before triggering a quality issue."""
    val = os.getenv("MAX_AGENT_TURNS", "5")
    try:
        return max(1, int(val))
    except ValueError:
        return 5
