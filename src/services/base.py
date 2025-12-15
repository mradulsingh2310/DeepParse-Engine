"""
Base Service Protocol for JSON Extraction.

Defines the unified interface that all extraction providers must implement.
"""

from typing import Protocol, TypeVar

from PIL import Image
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class JsonExtractionService(Protocol):
    """
    Unified interface for all JSON extraction providers.
    
    All providers take images as input and return a validated Pydantic model.
    The internal implementation details (OCR steps, API calls, etc.) are hidden.
    """
    
    def generate_json(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """
        Generate structured JSON from images.
        
        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class defining the output structure
            context: Optional template dictionary for additional context
            
        Returns:
            Validated Pydantic model instance with extracted data
        """
        ...

