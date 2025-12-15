"""
Logger Module.

Simple, generalized logging utility for OCR-AI.
"""

import logging
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("ocr-ai")


class UsageRecord(BaseModel):
    """Single usage record for an API call."""
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.now)
    operation: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class UsageTracker(BaseModel):
    """Tracks cumulative usage across multiple API calls."""
    records: list[UsageRecord] = []
    
    @property
    def total_cost_usd(self) -> float:
        return sum(r.cost_usd for r in self.records)
    
    def add(self, record: UsageRecord) -> None:
        """Add a usage record."""
        self.records.append(record)
    
    def summary(self) -> dict:
        """Get a summary of all usage."""
        by_provider: dict = {}
        for r in self.records:
            key = f"{r.provider}/{r.model}"
            if key not in by_provider:
                by_provider[key] = {"calls": 0, "tokens": 0, "cost": 0.0}
            by_provider[key]["calls"] += 1
            by_provider[key]["tokens"] += r.total_tokens
            by_provider[key]["cost"] += r.cost_usd
        
        return {
            "by_provider": by_provider,
            "total_calls": len(self.records),
            "total_cost": self.total_cost_usd
        }
    
    def print_summary(self) -> None:
        """Print a formatted usage summary."""
        s = self.summary()
        log("=" * 50)
        log("USAGE SUMMARY")
        for provider, stats in s["by_provider"].items():
            log(f"  {provider}: {stats['calls']} calls, {stats['tokens']:,} tokens, ${stats['cost']:.4f}")
        log(f"Total: {s['total_calls']} calls, ${s['total_cost']:.4f}")
        log("=" * 50)


# Global tracker holder (avoids global statement)
_tracker_holder: dict[str, UsageTracker] = {"tracker": UsageTracker()}


def get_tracker() -> UsageTracker:
    """Get the global usage tracker."""
    return _tracker_holder["tracker"]


def reset_tracker() -> None:
    """Reset the global usage tracker."""
    _tracker_holder["tracker"] = UsageTracker()


def log(message: str) -> None:
    """Log an info message."""
    logger.info(message)


def log_debug(message: str) -> None:
    """Log a debug message."""
    logger.debug(message)


def log_warning(message: str) -> None:
    """Log a warning message."""
    logger.warning(message)


def log_error(message: str) -> None:
    """Log an error message."""
    logger.error(message)


def log_usage(
    provider: str,
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cost_usd: float = 0.0,
    operation: str = "",
    **metadata: Any
) -> UsageRecord:
    """
    Log API usage for any provider.
    
    Args:
        provider: Provider name (e.g., "bedrock", "openai", "ollama")
        model: Model identifier
        input_tokens: Number of input tokens
        output_tokens: Number of output tokens
        cost_usd: Cost in USD
        operation: Description of the operation
        **metadata: Any additional metadata to log
        
    Returns:
        The created UsageRecord
    """
    record = UsageRecord(
        provider=provider,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        cost_usd=cost_usd,
        operation=operation,
        metadata=metadata
    )
    
    _tracker_holder["tracker"].add(record)
    
    log(f"[{provider}/{model}] {operation}")
    if input_tokens or output_tokens:
        log(f"  Tokens: {input_tokens:,} in / {output_tokens:,} out")
    if cost_usd > 0:
        log(f"  Cost: ${cost_usd:.6f}")
    
    return record
