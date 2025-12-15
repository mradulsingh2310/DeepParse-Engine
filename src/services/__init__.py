"""
Services module for OCR-AI.

Provides the JSON extraction service interface and factory.
"""

from .base import JsonExtractionService
from .factory import get_service

__all__ = [
    "JsonExtractionService",
    "get_service",
]

