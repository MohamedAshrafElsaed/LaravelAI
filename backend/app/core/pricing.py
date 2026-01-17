"""
AI Model Pricing Configuration.

Defines pricing per token for various AI providers and models.
Used for calculating API call costs in usage tracking.
"""
from typing import Dict, Optional
from decimal import Decimal


# Pricing per token (USD)
# Format: {provider: {model: {input: price, output: price}}}
PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    "claude": {
        "claude-haiku-4-5-20251001": {
            "input": 0.80 / 1_000_000,   # $0.80 per 1M tokens
            "output": 4.00 / 1_000_000,  # $4.00 per 1M tokens
        },
        "claude-sonnet-4-5-20250929": {
            "input": 3.00 / 1_000_000,   # $3.00 per 1M tokens
            "output": 15.00 / 1_000_000, # $15.00 per 1M tokens
        },
        "claude-opus-4-5-20251101": {
            "input": 15.00 / 1_000_000,  # $15.00 per 1M tokens
            "output": 75.00 / 1_000_000, # $75.00 per 1M tokens
        },
    },
    "openai": {
        "gpt-4o": {
            "input": 2.50 / 1_000_000,   # $2.50 per 1M tokens
            "output": 10.00 / 1_000_000, # $10.00 per 1M tokens
        },
        "gpt-4o-mini": {
            "input": 0.15 / 1_000_000,   # $0.15 per 1M tokens
            "output": 0.60 / 1_000_000,  # $0.60 per 1M tokens
        },
        "text-embedding-3-small": {
            "input": 0.02 / 1_000_000,   # $0.02 per 1M tokens
            "output": 0,
        },
        "text-embedding-3-large": {
            "input": 0.13 / 1_000_000,   # $0.13 per 1M tokens
            "output": 0,
        },
    },
    "voyage": {
        "voyage-code-3": {
            "input": 0.06 / 1_000_000,   # $0.06 per 1M tokens
            "output": 0,
        },
    },
}


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int = 0
) -> dict:
    """
    Calculate cost for an API call.

    Args:
        provider: AI provider (claude, openai, voyage)
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens (default 0 for embeddings)

    Returns:
        Dict with input_cost, output_cost, and total_cost (all rounded to 6 decimals)
    """
    pricing = PRICING.get(provider, {}).get(model)

    if not pricing:
        return {
            "input_cost": 0.0,
            "output_cost": 0.0,
            "total_cost": 0.0,
        }

    input_cost = input_tokens * pricing["input"]
    output_cost = output_tokens * pricing["output"]

    return {
        "input_cost": round(input_cost, 6),
        "output_cost": round(output_cost, 6),
        "total_cost": round(input_cost + output_cost, 6),
    }


def get_model_pricing(provider: str, model: str) -> Optional[Dict[str, float]]:
    """
    Get pricing info for a specific model.

    Args:
        provider: AI provider
        model: Model identifier

    Returns:
        Dict with input and output prices per token, or None if not found
    """
    return PRICING.get(provider, {}).get(model)


def estimate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    estimated_output_tokens: int = 1000
) -> dict:
    """
    Estimate cost before making an API call.

    Args:
        provider: AI provider
        model: Model identifier
        input_tokens: Known input token count
        estimated_output_tokens: Estimated output tokens (default 1000)

    Returns:
        Dict with estimated input_cost, output_cost, and total_cost
    """
    return calculate_cost(provider, model, input_tokens, estimated_output_tokens)


def get_supported_providers() -> list:
    """Get list of supported AI providers."""
    return list(PRICING.keys())


def get_supported_models(provider: str) -> list:
    """Get list of supported models for a provider."""
    return list(PRICING.get(provider, {}).keys())
