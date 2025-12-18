"""
Google AI Service Implementation.

Uses Google's Gemini models (e.g., Gemini 3 Flash) to extract structured JSON
directly from images in a single LLM request.
"""

import io
import json
import os
from typing import Any, TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import types
from PIL import Image
from pydantic import BaseModel

from src.config.loader import GoogleConfig, ModelConfig
from src.schemas.inspection import (
    MaintenanceCategory,
    WorkOrderSubCategory,
)
from src.services.providers.bedrock import EXTRACTION_PROMPT, normalize_enum_values
from src.utils.logger import log, log_usage

# Load environment variables from .env file
load_dotenv()

T = TypeVar("T", bound=BaseModel)


class GoogleError(Exception):
    """Base exception for Google AI-related errors."""


class GoogleConnectionError(GoogleError):
    """Raised when unable to connect to Google AI."""


class GoogleModelError(GoogleError):
    """Raised when the model is not available or fails."""


class GoogleService:
    """
    Google AI implementation of JsonExtractionService.

    Sends images directly to Google Gemini models for JSON extraction
    in a single request (no separate OCR step).
    """

    def __init__(
        self,
        config: GoogleConfig | None = None,
        model_config: ModelConfig | None = None,
    ):
        """
        Initialize GoogleService with configuration.

        Args:
            config: GoogleConfig instance. Uses defaults if not provided.
            model_config: ModelConfig with model_id to use. If not provided,
                         uses first model from config or a default.
        """
        self.config = config or GoogleConfig()

        # Determine which model to use
        if model_config is not None:
            self.model_id = model_config.model_id
        elif self.config.models:
            self.model_id = self.config.models[0].model_id
        else:
            # Fallback default
            self.model_id = "gemini-3-flash-preview"

        self._client = None

    def _get_client(self) -> genai.Client:
        """Get or create the Gemini client."""
        if self._client is None:
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise GoogleConnectionError(
                    "GOOGLE_API_KEY environment variable not set"
                )

            try:
                self._client = genai.Client(api_key=api_key)
            except Exception as e:
                raise GoogleConnectionError(
                    f"Failed to create Google AI client: {e}"
                ) from e

        return self._client

    def generate_json(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """
        Generate structured JSON from images using Google AI.

        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context

        Returns:
            Validated Pydantic model instance with extracted data
        """
        log(f"Extracting JSON from {len(images)} image(s) using Google AI [{self.model_id}]")

        client = self._get_client()

        # Generate JSON schema from Pydantic model
        json_schema = schema.model_json_schema()

        # Get enum values as strings for the prompt
        maintenance_categories = [cat.value for cat in MaintenanceCategory]
        work_order_subcategories = [sub.value for sub in WorkOrderSubCategory]

        # Build the prompt
        prompt = EXTRACTION_PROMPT.format(
            json_schema=json.dumps(json_schema, indent=2),
            template_context=json.dumps(context, indent=2) if context else "N/A",
            maintenance_categories=json.dumps(maintenance_categories, indent=2),
            work_order_subcategories=json.dumps(work_order_subcategories, indent=2),
        )

        # Build content parts: text prompt first, then all images
        content_parts: list[Any] = [prompt]

        for i, img in enumerate(images):
            log(f"Adding image {i + 1}/{len(images)} to request...")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()

            # Create Part object for the image
            content_parts.append(
                types.Part.from_bytes(
                    data=image_bytes,
                    mime_type="image/png",
                )
            )

        # Send request to Google AI
        try:
            log("Sending request to Google AI...")
            response = client.models.generate_content(
                model=self.model_id,
                contents=content_parts,
                config=types.GenerateContentConfig(
                    max_output_tokens=self.config.max_output_tokens,
                    temperature=0,
                ),
            )
        except Exception as e:
            log(f"Google AI error: {e}")
            raise GoogleModelError(f"Google AI API error: {e}") from e

        # Log usage if available
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            usage = response.usage_metadata
            input_tokens = getattr(usage, "prompt_token_count", 0)
            output_tokens = getattr(usage, "candidates_token_count", 0)

            log_usage(
                provider="google",
                model=self.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation="image_to_json_extraction",
            )

        # Extract response text
        try:
            result_text = response.text
        except (AttributeError, ValueError) as e:
            log(f"Failed to extract response text: {e}")
            raise GoogleModelError(
                f"Invalid response structure from Google AI: {e}"
            ) from e

        # Parse JSON from response (handle markdown code blocks)
        result_text = result_text.strip()
        if result_text.startswith("```json"):
            result_text = result_text[7:]
        if result_text.startswith("```"):
            result_text = result_text[3:]
        if result_text.endswith("```"):
            result_text = result_text[:-3]
        result_text = result_text.strip()

        # Validate against Pydantic model
        try:
            result_dict = json.loads(result_text)
        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON response: {e}")
            log(f"Response text: {result_text[:2000]}...")
            raise GoogleModelError(f"Invalid JSON in response: {e}") from e

        # Normalize enum values to fix casing issues from LLM
        result_dict = normalize_enum_values(result_dict)

        # Always log the raw response for debugging
        log("Raw response from Google AI (normalized):")
        print(json.dumps(result_dict, indent=2))
        log("Extraction completed successfully")
        return result_dict
