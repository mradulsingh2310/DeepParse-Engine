"""
Anthropic Service Implementation.

Uses Anthropic's Claude models (e.g., Claude 4.5 Haiku) to extract structured JSON
directly from images in a single LLM request.

Supports structured outputs via the beta API (structured-outputs-2025-11-13) to
guarantee valid JSON responses matching the provided schema.

Reference: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
"""

import base64
import io
import json
import os
from typing import Any, TypeVar

import anthropic
from anthropic import transform_schema
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel

from src.config.loader import AnthropicConfig, ModelConfig
from src.schemas.inspection import (
    MaintenanceCategory,
    WorkOrderSubCategory,
)
from src.services.providers.bedrock import normalize_enum_values
from src.utils.prompts import VISION_EXTRACTION_PROMPT_ANTHROPIC
from src.utils.logger import log, log_usage

# Load environment variables from .env file
load_dotenv()

T = TypeVar("T", bound=BaseModel)

# Beta feature for structured outputs - guarantees valid JSON matching schema
STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"


class AnthropicError(Exception):
    """Base exception for Anthropic-related errors."""


class AnthropicConnectionError(AnthropicError):
    """Raised when unable to connect to Anthropic."""


class AnthropicModelError(AnthropicError):
    """Raised when the model is not available or fails."""


class AnthropicService:
    """
    Anthropic implementation of JsonExtractionService.

    Sends images directly to Anthropic Claude models for JSON extraction
    in a single request (no separate OCR step).
    """

    def __init__(
        self,
        config: AnthropicConfig | None = None,
        model_config: ModelConfig | None = None,
    ):
        """
        Initialize AnthropicService with configuration.

        Args:
            config: AnthropicConfig instance. Uses defaults if not provided.
            model_config: ModelConfig with model_id to use. If not provided,
                         uses first model from config or a default.
        """
        self.config = config or AnthropicConfig()

        # Determine which model to use
        if model_config is not None:
            self.model_id = model_config.model_id
        elif self.config.models:
            self.model_id = self.config.models[0].model_id
        else:
            # Fallback default
            self.model_id = "claude-haiku-4-5-20251001"

        self._client = None

    def _get_client(self) -> anthropic.Anthropic:
        """Get or create the Anthropic client."""
        if self._client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise AnthropicConnectionError(
                    "ANTHROPIC_API_KEY environment variable not set"
                )

            try:
                self._client = anthropic.Anthropic(
                    api_key=api_key,
                    timeout=self.config.timeout,
                )
            except Exception as e:
                raise AnthropicConnectionError(
                    f"Failed to create Anthropic client: {e}"
                ) from e

        return self._client

    def generate_json(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """
        Generate structured JSON from images using Anthropic with structured outputs.

        Uses the structured outputs beta API to guarantee valid JSON matching the schema.
        Reference: https://platform.claude.com/docs/en/build-with-claude/structured-outputs

        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context

        Returns:
            Validated Pydantic model instance with extracted data
        """
        log(f"Extracting JSON from {len(images)} image(s) using Anthropic [{self.model_id}] with structured outputs")

        client = self._get_client()

        # Get enum values as strings for the prompt
        maintenance_categories = [cat.value for cat in MaintenanceCategory]
        work_order_subcategories = [sub.value for sub in WorkOrderSubCategory]

        # Build the prompt - schema is enforced by output_format, so prompt focuses on extraction rules
        prompt = VISION_EXTRACTION_PROMPT_ANTHROPIC.format(
            template_context=json.dumps(context, indent=2) if context else "N/A",
            maintenance_categories=json.dumps(maintenance_categories, indent=2),
            work_order_subcategories=json.dumps(work_order_subcategories, indent=2),
        )

        # Build content parts: images first, then text prompt (Anthropic convention)
        content: list[dict[str, Any]] = []

        for i, img in enumerate(images):
            log(f"Adding image {i + 1}/{len(images)} to request...")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # Anthropic expects images in this format
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": image_base64,
                },
            })

        # Add the text prompt after images
        content.append({"type": "text", "text": prompt})

        # Transform Pydantic schema for Anthropic structured outputs
        # This handles unsupported features by adding constraints to field descriptions
        transformed_schema = transform_schema(schema)
        log(f"Using structured outputs with schema: {schema.__name__}")

        # Send request to Anthropic using beta API with structured outputs
        try:
            log("Sending request to Anthropic with structured outputs...")
            response = client.beta.messages.create(
                model=self.model_id,
                max_tokens=self.config.max_tokens,
                betas=[STRUCTURED_OUTPUTS_BETA],
                messages=[{"role": "user", "content": content}],
                output_format={
                    "type": "json_schema",
                    "schema": transformed_schema,
                },
            )
        except anthropic.APIError as e:
            log(f"Anthropic API error: {e}")
            raise AnthropicModelError(f"Anthropic API error: {e}") from e
        except Exception as e:
            log(f"Unexpected error calling Anthropic: {e}")
            raise AnthropicError(f"Unexpected error calling Anthropic: {e}") from e

        # Check for refusals or truncation
        if hasattr(response, "stop_reason"):
            if response.stop_reason == "refusal":
                log("WARNING: Claude refused the request for safety reasons")
                raise AnthropicModelError("Claude refused the request for safety reasons")
            elif response.stop_reason == "max_tokens":
                log("WARNING: Response was truncated due to max_tokens limit")
                raise AnthropicModelError(
                    f"Response truncated - max_tokens ({self.config.max_tokens}) insufficient. "
                    "Increase max_tokens in config."
                )

        # Log usage
        if hasattr(response, "usage") and response.usage:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            log_usage(
                provider="anthropic",
                model=self.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation="image_to_json_extraction",
            )

        # Extract response text - structured outputs guarantees valid JSON
        try:
            result_text = response.content[0].text
        except (KeyError, IndexError, AttributeError) as e:
            log(f"Failed to extract response text: {e}")
            raise AnthropicModelError(
                f"Invalid response structure from Anthropic: {e}"
            ) from e

        # Parse JSON - should always be valid due to structured outputs
        try:
            result_dict = json.loads(result_text)
        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON response: {e}")
            log(f"Response text: {result_text[:2000]}...")
            raise AnthropicModelError(f"Invalid JSON in response: {e}") from e

        # Normalize enum values to fix casing issues from LLM
        result_dict = normalize_enum_values(result_dict)
        
        log("Extraction completed successfully")
        return result_dict
