"""
Model Pricing Configuration.

Pricing data for all supported providers and models.
Prices are per million tokens (input and output).
"""

# Pricing per million tokens (USD)
PRICING_PER_MILLION: dict[str, dict[str, dict[str, float]]] = {
    "openai": {
        "gpt-5": {"input": 1.25, "output": 10.00},
        "gpt-5.2": {"input": 2.50, "output": 15.00},
        "gpt-5-mini": {"input": 0.25, "output": 2.00},
        "gpt-5-nano": {"input": 0.05, "output": 0.40},
    },
    "google": {
        "gemini-2.5-flash": {"input": 0.30, "output": 2.50},
        "gemini-2.5-flash-image": {"input": 0.30, "output": 2.50},
        "gemini-3-flash-preview": {"input": 0.30, "output": 2.50},
    },
    "bedrock": {
        "amazon.nova-pro-v1:0": {"input": 0.80, "output": 3.20},
        "qwen.qwen3-vl-235b-a22b": {"input": 0.18, "output": 0.54},
        "google.gemma-3-27b-it": {"input": 0.15, "output": 0.60},
        "nvidia.nemotron-nano-12b-v2": {"input": 0.06, "output": 0.24},
    },
    "anthropic": {
        "claude-sonnet-4-5-20250929": {"input": 3.00, "output": 15.00},
        "claude-haiku-4-5-20251001": {"input": 0.80, "output": 4.00},
    },
    "deepseek": {
        "deepseek-ocr": {"input": 0.0, "output": 0.0},  # Local Ollama - free
    },
}


def calculate_cost(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """
    Calculate cost in USD based on token usage.

    Args:
        provider: Provider name (e.g., "openai", "google", "bedrock")
        model: Model identifier (e.g., "gpt-5", "gemini-2.5-flash")
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens

    Returns:
        Cost in USD. Returns 0.0 if provider/model not found.
    """
    pricing = PRICING_PER_MILLION.get(provider, {}).get(model)
    if not pricing:
        return 0.0  # Unknown model, return 0

    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost


def get_pricing(provider: str, model: str) -> dict[str, float] | None:
    """
    Get pricing info for a provider/model.

    Args:
        provider: Provider name
        model: Model identifier

    Returns:
        Dict with "input" and "output" prices per million tokens, or None if not found.
    """
    return PRICING_PER_MILLION.get(provider, {}).get(model)
