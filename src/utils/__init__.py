"""
Utility modules for OCR-AI.

Contains PDF processing, logging, and other helper functions.
"""

from .pdf import pdf_to_images
from .logger import (
    log,
    log_debug,
    log_warning,
    log_error,
    log_usage,
    get_tracker,
    reset_tracker,
    UsageTracker,
    UsageRecord,
)

__all__ = [
    # PDF utilities
    "pdf_to_images",
    # Logging utilities
    "log",
    "log_debug",
    "log_warning",
    "log_error",
    "log_usage",
    "get_tracker",
    "reset_tracker",
    "UsageTracker",
    "UsageRecord",
]
