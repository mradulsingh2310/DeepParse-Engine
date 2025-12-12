"""
Usage Logger Module

Tracks and logs token usage and cost for AI model API calls.
"""

import logging
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("usage_logger")

# Pricing per 1M tokens (as of Dec 2024)
# OpenAI: https://openai.com/pricing
OPENAI_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    "gpt-4": {"input": 30.00, "output": 60.00},
    "gpt-3.5-turbo": {"input": 0.50, "output": 1.50},
    "gpt-5.1": {"input": 2.50, "output": 10.00},  # Assuming same as gpt-4o
    "gpt-5.2": {"input": 2.50, "output": 10.00},  # Assuming same as gpt-4o
}

# Ollama/DeepSeek runs locally - no API cost, but we track tokens for context
OLLAMA_PRICING = {
    "deepseek-ocr": {"input": 0.0, "output": 0.0},  # Local model - free
}


class UsageRecord(BaseModel):
    """Single usage record for an API call."""
    provider: Literal["openai", "ollama"]
    model: str
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cost_usd: float
    timestamp: datetime = Field(default_factory=datetime.now)
    operation: str = ""


class UsageTracker(BaseModel):
    """Tracks cumulative usage across multiple API calls."""
    records: list[UsageRecord] = []
    
    @property
    def total_input_tokens(self) -> int:
        return sum(r.input_tokens for r in self.records)
    
    @property
    def total_output_tokens(self) -> int:
        return sum(r.output_tokens for r in self.records)
    
    @property
    def total_tokens(self) -> int:
        return sum(r.total_tokens for r in self.records)
    
    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)
    
    def add_record(self, record: UsageRecord) -> None:
        self.records.append(record)
    
    def get_summary(self) -> dict:
        """Get a summary of all usage."""
        by_provider: dict = {}
        for r in self.records:
            key = f"{r.provider}/{r.model}"
            if key not in by_provider:
                by_provider[key] = {
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "total_tokens": 0,
                    "cost_usd": 0.0
                }
            by_provider[key]["calls"] += 1
            by_provider[key]["input_tokens"] += r.input_tokens
            by_provider[key]["output_tokens"] += r.output_tokens
            by_provider[key]["total_tokens"] += r.total_tokens
            by_provider[key]["cost_usd"] += r.cost_usd
        
        return {
            "by_provider": by_provider,
            "totals": {
                "calls": len(self.records),
                "input_tokens": self.total_input_tokens,
                "output_tokens": self.total_output_tokens,
                "total_tokens": self.total_tokens,
                "cost_usd": self.total_cost_usd
            }
        }
    
    def print_summary(self) -> None:
        """Print a formatted usage summary."""
        summary = self.get_summary()
        
        logger.info("=" * 60)
        logger.info("USAGE SUMMARY")
        logger.info("=" * 60)
        
        for provider, stats in summary["by_provider"].items():
            logger.info("  %s:", provider)
            logger.info("    Calls: %d", stats["calls"])
            logger.info("    Input tokens: %s", f"{stats['input_tokens']:,}")
            logger.info("    Output tokens: %s", f"{stats['output_tokens']:,}")
            logger.info("    Total tokens: %s", f"{stats['total_tokens']:,}")
            logger.info("    Cost: $%.6f", stats["cost_usd"])
        
        logger.info("-" * 60)
        totals = summary["totals"]
        logger.info("TOTAL:")
        logger.info("  Calls: %d", totals["calls"])
        logger.info("  Input tokens: %s", f"{totals['input_tokens']:,}")
        logger.info("  Output tokens: %s", f"{totals['output_tokens']:,}")
        logger.info("  Total tokens: %s", f"{totals['total_tokens']:,}")
        logger.info("  Cost: $%.6f", totals["cost_usd"])
        logger.info("=" * 60)


# Global tracker instance (use a dict to avoid global statement)
_tracker_holder: dict[str, UsageTracker] = {"tracker": UsageTracker()}


def get_tracker() -> UsageTracker:
    """Get the global usage tracker."""
    return _tracker_holder["tracker"]


def reset_tracker() -> None:
    """Reset the global usage tracker."""
    _tracker_holder["tracker"] = UsageTracker()


def calculate_cost(model: str, input_tokens: int, output_tokens: int, provider: str) -> float:
    """Calculate cost in USD for the given token usage."""
    pricing = OPENAI_PRICING if provider == "openai" else OLLAMA_PRICING
    
    if model not in pricing:
        logger.warning("Unknown model '%s' for %s, using zero cost", model, provider)
        return 0.0
    
    rates = pricing[model]
    input_cost = (input_tokens / 1_000_000) * rates["input"]
    output_cost = (output_tokens / 1_000_000) * rates["output"]
    return input_cost + output_cost

def log (message: str) -> None:
    logger.info(message)

def log_openai_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    operation: str = "chat_completion"
) -> UsageRecord:
    """Log OpenAI API usage and return the record."""
    cost = calculate_cost(model, input_tokens, output_tokens, "openai")
    
    record = UsageRecord(
        provider="openai",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        operation=operation
    )
    
    get_tracker().add_record(record)
    
    logger.info("OpenAI [%s] - %s", model, operation)
    logger.info("  Tokens: %s input / %s output / %s total",
                f"{input_tokens:,}", f"{output_tokens:,}", f"{total_tokens:,}")
    logger.info("  Cost: $%.6f", cost)
    
    return record


def log_ollama_usage(
    model: str,
    input_tokens: int,
    output_tokens: int,
    total_tokens: int,
    operation: str = "ocr"
) -> UsageRecord:
    """Log Ollama/DeepSeek usage and return the record."""
    cost = calculate_cost(model, input_tokens, output_tokens, "ollama")
    
    record = UsageRecord(
        provider="ollama",
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=cost,
        operation=operation
    )
    
    get_tracker().add_record(record)
    
    logger.info("Ollama [%s] - %s", model, operation)
    logger.info("  Tokens: %s input / %s output / %s total",
                f"{input_tokens:,}", f"{output_tokens:,}", f"{total_tokens:,}")
    logger.info("  Cost: $%.6f (local model)", cost)
    
    return record

