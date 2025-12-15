"""
OCR-AI: PDF to Structured JSON Pipeline.

A service-based architecture for extracting structured JSON from images
using various AI providers (AWS Bedrock, DeepSeek + OpenAI).
"""

from .config import Provider, load_config, get_config
from .services import get_service, JsonExtractionService
from .schemas import InspectionTemplate
from .utils import pdf_to_images, log, get_tracker, reset_tracker

__all__ = [
    # Config
    "Provider",
    "load_config",
    "get_config",
    # Services
    "get_service",
    "JsonExtractionService",
    # Schemas
    "InspectionTemplate",
    # Utils
    "pdf_to_images",
    "log",
    "get_tracker",
    "reset_tracker",
]
