"""
OpenAI Service Implementation.

Uses OpenAI's GPT models (e.g., GPT-5, GPT-5.2) to extract structured JSON
directly from images in a single LLM request.

Supports structured outputs via response_format with json_schema to
guarantee valid JSON responses matching the provided schema.

Reference: https://platform.openai.com/docs/guides/structured-outputs
"""

import base64
import io
import json
import os
from typing import Any, TypeVar

import openai
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel

from src.config.loader import OpenAIConfig, ModelConfig
from src.schemas.inspection import (
    MaintenanceCategory,
    WorkOrderSubCategory,
)
from src.services.providers.bedrock import normalize_enum_values
from src.utils.logger import log, log_usage
from src.utils.merge import merge_section_responses
from src.utils.prompts import (
    VISION_EXTRACTION_PROMPT_ANTHROPIC,
    VISION_EXTRACTION_PROMPT_ANTHROPIC_CONTINUATION,
)

# Load environment variables from .env file
load_dotenv()

T = TypeVar("T", bound=BaseModel)


class OpenAIError(Exception):
    """Base exception for OpenAI-related errors."""


class OpenAIConnectionError(OpenAIError):
    """Raised when unable to connect to OpenAI."""


class OpenAIModelError(OpenAIError):
    """Raised when the model is not available or fails."""


def _pydantic_to_strict_schema(schema: type[BaseModel]) -> dict[str, Any]:
    """
    Convert a Pydantic model to OpenAI strict JSON schema format.

    OpenAI structured outputs require:
    - additionalProperties: false on all objects
    - All properties must be in "required" array
    - No optional fields

    Args:
        schema: Pydantic model class

    Returns:
        JSON schema dict compatible with OpenAI structured outputs
    """
    json_schema = schema.model_json_schema()

    def make_strict(obj: Any) -> Any:
        """Recursively make schema strict for OpenAI."""
        if isinstance(obj, dict):
            # OpenAI strict mode: $ref cannot have additional keywords like 'default'
            if "$ref" in obj and "default" in obj:
                obj = {k: v for k, v in obj.items() if k != "default"}

            result = {}
            for key, value in obj.items():
                result[key] = make_strict(value)

            # If this is an object type, make it strict
            if result.get("type") == "object" and "properties" in result:
                result["additionalProperties"] = False
                # All properties must be required
                if "properties" in result:
                    result["required"] = list(result["properties"].keys())

            return result
        elif isinstance(obj, list):
            return [make_strict(item) for item in obj]
        return obj

    # Process definitions/refs if present
    if "$defs" in json_schema:
        json_schema["$defs"] = {
            k: make_strict(v) for k, v in json_schema["$defs"].items()
        }

    return make_strict(json_schema)


class OpenAIService:
    """
    OpenAI implementation of JsonExtractionService.

    Sends images directly to OpenAI GPT models for JSON extraction
    in a single request (no separate OCR step).
    """

    def __init__(
        self,
        config: OpenAIConfig | None = None,
        model_config: ModelConfig | None = None,
    ):
        """
        Initialize OpenAIService with configuration.

        Args:
            config: OpenAIConfig instance. Uses defaults if not provided.
            model_config: ModelConfig with model_id to use. If not provided,
                         uses first model from config or a default.
        """
        self.config = config or OpenAIConfig()

        # Determine which model to use
        if model_config is not None:
            self.model_id = model_config.model_id
        elif self.config.models:
            self.model_id = self.config.models[0].model_id
        else:
            # Fallback default
            self.model_id = "gpt-5-mini"

        self._client: openai.OpenAI | None = None

    def _get_client(self) -> openai.OpenAI:
        """Get or create the OpenAI client."""
        if self._client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                raise OpenAIConnectionError(
                    "OPENAI_API_KEY environment variable not set"
                )

            try:
                self._client = openai.OpenAI(
                    api_key=api_key,
                    timeout=self.config.timeout,
                )
            except Exception as e:
                raise OpenAIConnectionError(
                    f"Failed to create OpenAI client: {e}"
                ) from e

        return self._client

    def generate_json(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """
        Generate structured JSON from images using OpenAI with structured outputs.

        If the number of images exceeds chunk_size, processes in batches
        and merges the results.

        Uses the response_format parameter with json_schema to guarantee valid JSON
        matching the schema.
        Reference: https://platform.openai.com/docs/guides/structured-outputs

        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context

        Returns:
            Validated Pydantic model instance with extracted data
        """
        chunk_size = self.config.chunk_size
        total_images = len(images)

        log(f"Extracting JSON from {total_images} image(s) using OpenAI [{self.model_id}] with structured outputs")

        # If images fit in a single chunk, process directly
        if total_images <= chunk_size:
            return self._generate_json_chunk(
                images=images,
                schema=schema,
                context=context,
                chunk_info=None,
            )

        # Process in chunks and merge
        log(f"Document has {total_images} pages, processing in chunks of {chunk_size}...")

        chunks: list[list[Image.Image]] = []
        for i in range(0, total_images, chunk_size):
            chunks.append(images[i:i + chunk_size])

        total_chunks = len(chunks)
        log(f"Split into {total_chunks} chunks")

        # Process each chunk
        chunk_responses: list[dict] = []
        current_page = 1

        for chunk_idx, chunk_images in enumerate(chunks):
            chunk_number = chunk_idx + 1
            page_start = current_page
            page_end = current_page + len(chunk_images) - 1

            log(f"Processing chunk {chunk_number}/{total_chunks} (pages {page_start}-{page_end})...")

            chunk_info = {
                "chunk_number": chunk_number,
                "total_chunks": total_chunks,
                "page_start": page_start,
                "page_end": page_end,
                "total_pages": total_images,
            }

            chunk_result = self._generate_json_chunk(
                images=chunk_images,
                schema=schema,
                context=context,
                chunk_info=chunk_info,
            )
            chunk_responses.append(chunk_result)
            current_page = page_end + 1

        # Merge all chunk responses
        log(f"Merging {len(chunk_responses)} chunk responses...")
        merged_result = merge_section_responses(chunk_responses)

        log("Chunked extraction and merge completed successfully")
        return merged_result

    def _generate_json_chunk(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
        chunk_info: dict | None = None,
    ) -> dict:
        """
        Generate JSON from a single chunk of images.

        Args:
            images: List of PIL Images for this chunk
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context
            chunk_info: Optional dict with chunk_number, total_chunks, page_start,
                       page_end, total_pages for continuation prompts

        Returns:
            Extracted data as dict (not yet validated against schema)
        """
        client = self._get_client()

        # Get enum values as strings for the prompt
        maintenance_categories = [cat.value for cat in MaintenanceCategory]
        work_order_subcategories = [sub.value for sub in WorkOrderSubCategory]

        # Build the prompt - use continuation prompt for chunk 2+
        if chunk_info and chunk_info["chunk_number"] > 1:
            prompt = VISION_EXTRACTION_PROMPT_ANTHROPIC_CONTINUATION.format(
                chunk_number=chunk_info["chunk_number"],
                total_chunks=chunk_info["total_chunks"],
                page_start=chunk_info["page_start"],
                page_end=chunk_info["page_end"],
                total_pages=chunk_info["total_pages"],
                template_context=json.dumps(context, indent=2) if context else "N/A",
                maintenance_categories=json.dumps(maintenance_categories, indent=2),
                work_order_subcategories=json.dumps(work_order_subcategories, indent=2),
            )
        else:
            prompt = VISION_EXTRACTION_PROMPT_ANTHROPIC.format(
                template_context=json.dumps(context, indent=2) if context else "N/A",
                maintenance_categories=json.dumps(maintenance_categories, indent=2),
                work_order_subcategories=json.dumps(work_order_subcategories, indent=2),
            )

        # Build content parts: text prompt first, then images (OpenAI convention)
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        for i, img in enumerate(images):
            log(f"Adding image {i + 1}/{len(images)} to request...")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            image_base64 = base64.b64encode(image_bytes).decode("utf-8")

            # OpenAI expects images in this format
            content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_base64}",
                    "detail": "high",  # Use high detail for document extraction
                },
            })

        # Transform Pydantic schema for OpenAI structured outputs
        strict_schema = _pydantic_to_strict_schema(schema)
        log(f"Using structured outputs with schema: {schema.__name__}")

        # Send request to OpenAI using Chat Completions with structured outputs
        try:
            log("Sending request to OpenAI with structured outputs...")
            request_params: dict[str, Any] = {
                "model": self.model_id,
                "max_completion_tokens": self.config.max_tokens,
                # Some models (e.g., gpt-5-mini) do not allow temperature overrides;
                # omit to use the model default.
                "messages": [{"role": "user", "content": content}],
                "response_format": {
                    "type": "json_schema",
                    "json_schema": {
                        "name": schema.__name__,
                        "schema": strict_schema,
                        "strict": True,
                    },
                },
            }
            # Type checkers may not understand the dynamic request dict, so we ignore typing here.
            response = client.chat.completions.create(**request_params)  # type: ignore
        except openai.APIError as e:
            log(f"OpenAI API error: {e}")
            raise OpenAIModelError(f"OpenAI API error: {e}") from e
        except Exception as e:
            log(f"Unexpected error calling OpenAI: {e}")
            raise OpenAIError(f"Unexpected error calling OpenAI: {e}") from e

        # Check for refusals or truncation
        choice = response.choices[0] if response.choices else None
        if choice:
            if choice.finish_reason == "content_filter":
                log("WARNING: OpenAI refused the request due to content filtering")
                raise OpenAIModelError("OpenAI refused the request due to content filtering")
            elif choice.finish_reason == "length":
                log("WARNING: Response was truncated due to completion token limit")
                raise OpenAIModelError(
                    f"Response truncated - completion token limit ({self.config.max_tokens}) insufficient. "
                    "Increase max_tokens in config (sent as max_completion_tokens)."
                )

        # Log usage
        if response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            log_usage(
                provider="openai",
                model=self.model_id,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation="image_to_json_extraction",
            )

        # Extract response text - structured outputs guarantees valid JSON
        try:
            result_text = response.choices[0].message.content
        except (KeyError, IndexError, AttributeError) as e:
            log(f"Failed to extract response text: {e}")
            raise OpenAIModelError(
                f"Invalid response structure from OpenAI: {e}"
            ) from e

        # Parse JSON - should always be valid due to structured outputs
        try:
            result_dict = json.loads(result_text)
        except json.JSONDecodeError as e:
            log(f"Failed to parse JSON response: {e}")
            log(f"Response text: {result_text[:2000]}...")
            raise OpenAIModelError(f"Invalid JSON in response: {e}") from e

        # Normalize enum values to fix casing issues from LLM
        result_dict = normalize_enum_values(result_dict)

        log("Chunk extraction completed successfully")
        return result_dict
