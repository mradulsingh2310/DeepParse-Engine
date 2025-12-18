"""
AWS Bedrock Service Implementation.

Uses AWS Bedrock vision models (e.g., Qwen3 VL) to extract structured JSON
directly from images in a single LLM request.
"""

import io
import json
import os
from typing import Any, TypeVar

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from dotenv import load_dotenv
from PIL import Image
from pydantic import BaseModel

from src.config.loader import BedrockConfig, ModelConfig
from src.schemas.inspection import (
    MaintenanceCategory, 
    WorkOrderSubCategory,
)
from src.utils.logger import log, log_usage
from src.utils.merge import merge_section_responses
from src.utils.prompts import VISION_EXTRACTION_PROMPT, VISION_EXTRACTION_PROMPT_CONTINUATION

# Load environment variables from .env file
load_dotenv()

T = TypeVar("T", bound=BaseModel)


def normalize_enum_values(obj: Any) -> Any:
    """
    Recursively normalize enum field values to uppercase with underscores.
    
    Fixes common LLM mistakes like:
    - 'RATING_TYPE-select' -> 'RATING_TYPE_SELECT'
    - 'WORK_ORDER_SUB_CATEGORY_CARPENTRY_FLOORBOARD_REpair' -> 'WORK_ORDER_SUB_CATEGORY_CARPENTRY_FLOORBOARD_REPAIR'
    """
    # Fields that contain enum values needing normalization
    ENUM_FIELDS = {
        "rating_type",
        "work_order_category",
        "work_order_sub_category",
        "display_type",
    }
    
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key in ENUM_FIELDS and isinstance(value, str):
                # Normalize: replace hyphens with underscores, uppercase everything
                result[key] = value.replace("-", "_").upper()
            elif isinstance(value, (dict, list)):
                result[key] = normalize_enum_values(value)
            else:
                result[key] = value
        return result
    elif isinstance(obj, list):
        return [normalize_enum_values(item) if isinstance(item, (dict, list)) else item for item in obj]
    return obj


class BedrockError(Exception):
    """Base exception for Bedrock-related errors."""


class BedrockConnectionError(BedrockError):
    """Raised when unable to connect to Bedrock."""


class BedrockModelError(BedrockError):
    """Raised when the model is not available or fails."""


class BedrockService:
    """
    AWS Bedrock implementation of JsonExtractionService.
    
    Sends images directly to Bedrock vision models for JSON extraction
    in a single request (no separate OCR step).
    """
    
    def __init__(
        self,
        config: BedrockConfig | None = None,
        model_config: ModelConfig | None = None,
    ):
        """
        Initialize BedrockService with configuration.
        
        Args:
            config: BedrockConfig instance. Uses defaults if not provided.
            model_config: ModelConfig with model_id to use. If not provided,
                         uses first model from config or a default.
        """
        self.config = config or BedrockConfig()
        self._model_config = model_config
        
        # Determine which model to use
        if model_config is not None:
            self.model_id = model_config.model_id
        elif self.config.models:
            self.model_id = self.config.models[0].model_id
        else:
            # Fallback default
            self.model_id = "qwen.qwen3-vl-235b-a22b"
        
        self._client = None
    
    def _get_max_tokens(self) -> int:
        """Get max tokens, preferring per-model config over provider default."""
        if self._model_config and self._model_config.max_tokens is not None:
            return self._model_config.max_tokens
        return self.config.max_tokens
    
    def _get_client(self):
        """Get or create the Bedrock client."""
        if self._client is None:
            profile = os.getenv("AWS_PROFILE")
            region = os.getenv("AWS_REGION", self.config.region)
            
            bedrock_config = Config(
                read_timeout=self.config.timeout,
                connect_timeout=30,
                retries={"max_attempts": self.config.retries}
            )
            
            try:
                session = boto3.Session(profile_name=profile)
                self._client = session.client(
                    "bedrock-runtime",
                    region_name=region,
                    config=bedrock_config
                )
            except Exception as e:
                raise BedrockConnectionError(f"Failed to create Bedrock client: {e}") from e
        
        return self._client
    
    def generate_json(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """
        Generate structured JSON from images using AWS Bedrock.
        
        If the number of images exceeds chunk_size, processes in batches
        and merges the results.
        
        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context
            
        Returns:
            Validated Pydantic model instance with extracted data
        """
        chunk_size = self.config.chunk_size
        total_images = len(images)
        
        log(f"Extracting JSON from {total_images} image(s) using Bedrock [{self.model_id}]")
        
        # If images fit in a single chunk, process directly
        if total_images <= chunk_size:
            return self._generate_json_chunk(
                images=images,
                schema=schema,
                context=context,
                chunk_info=None,  # No chunking info needed
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
        
        # Generate JSON schema from Pydantic model
        json_schema = schema.model_json_schema()
        
        # Get enum values as strings for the prompt
        maintenance_categories = [cat.value for cat in MaintenanceCategory]
        work_order_subcategories = [sub.value for sub in WorkOrderSubCategory]
        
        # Build the prompt - use continuation prompt for chunk 2+
        if chunk_info and chunk_info["chunk_number"] > 1:
            prompt = VISION_EXTRACTION_PROMPT_CONTINUATION.format(
                chunk_number=chunk_info["chunk_number"],
                total_chunks=chunk_info["total_chunks"],
                page_start=chunk_info["page_start"],
                page_end=chunk_info["page_end"],
                total_pages=chunk_info["total_pages"],
                json_schema=json.dumps(json_schema, indent=2),
                template_context=json.dumps(context, indent=2) if context else "N/A",
                maintenance_categories=json.dumps(maintenance_categories, indent=2),
                work_order_subcategories=json.dumps(work_order_subcategories, indent=2),
            )
        else:
            prompt = VISION_EXTRACTION_PROMPT.format(
                json_schema=json.dumps(json_schema, indent=2),
                template_context=json.dumps(context, indent=2) if context else "N/A",
                maintenance_categories=json.dumps(maintenance_categories, indent=2),
                work_order_subcategories=json.dumps(work_order_subcategories, indent=2),
            )
        
        # Build content blocks: text prompt first, then all images
        content: list[dict] = [{"text": prompt}]
        
        # Track total request size for validation
        prompt_size_bytes = len(prompt.encode('utf-8'))
        total_image_size_bytes = 0
        MAX_IMAGE_SIZE_MB = 3.75 * 1024 * 1024  # 3.75 MB per image
        MAX_TOTAL_PAYLOAD_MB = 16 * 1024 * 1024  # 16 MB total payload (conservative estimate)
        
        for i, img in enumerate(images):
            log(f"Adding image {i + 1}/{len(images)} to request...")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            image_size_mb = len(image_bytes) / (1024 * 1024)
            
            # Check individual image size limit
            if len(image_bytes) > MAX_IMAGE_SIZE_MB:
                raise BedrockModelError(
                    f"Image {i + 1} exceeds Bedrock limit: {image_size_mb:.2f} MB "
                    f"(max 3.75 MB per image). Consider reducing image resolution or compression."
                )
            
            total_image_size_bytes += len(image_bytes)
            log(f"  Image {i + 1} size: {image_size_mb:.2f} MB")
            
            content.append({
                "image": {
                    "format": "png",
                    "source": {"bytes": image_bytes}
                }
            })
        
        # Check total payload size
        total_payload_bytes = prompt_size_bytes + total_image_size_bytes
        total_payload_mb = total_payload_bytes / (1024 * 1024)
        prompt_size_mb = prompt_size_bytes / (1024 * 1024)
        total_image_size_mb = total_image_size_bytes / (1024 * 1024)
        
        log("Request size breakdown:")
        log(f"  Prompt text: {prompt_size_mb:.2f} MB")
        log(f"  Total images ({len(images)}): {total_image_size_mb:.2f} MB")
        log(f"  Total payload: {total_payload_mb:.2f} MB (limit: ~16 MB)")
        
        if total_payload_bytes > MAX_TOTAL_PAYLOAD_MB:
            raise BedrockModelError(
                f"Total request payload ({total_payload_mb:.2f} MB) exceeds Bedrock limit (~16 MB). "
                f"Consider splitting the document into smaller batches or reducing image resolution."
            )
        
        # Send request to Bedrock
        try:
            log("Sending request to Bedrock...")
            response = client.converse(
                modelId=self.model_id,
                messages=[{"role": "user", "content": content}],
                inferenceConfig={
                    "maxTokens": self._get_max_tokens(),
                }
            )
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            log(f"Bedrock API error: {error_code} - {error_msg}")
            raise BedrockModelError(f"Bedrock API error [{error_code}]: {error_msg}") from e
        except Exception as e:
            log(f"Unexpected error calling Bedrock: {e}")
            raise BedrockError(f"Unexpected error calling Bedrock: {e}") from e
        
        # Log usage
        usage = response.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
        
        log_usage(
            provider="bedrock",
            model=self.model_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            operation="image_to_json_extraction"
        )
        
        # Extract response text
        try:
            output_message = response["output"]["message"]
            result_text = output_message["content"][0]["text"]
        except (KeyError, IndexError) as e:
            log(f"Failed to extract response text: {e}")
            raise BedrockModelError(f"Invalid response structure from Bedrock: {e}") from e
        
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
            raise BedrockModelError(f"Invalid JSON in response: {e}") from e
        
        # Normalize enum values to fix casing issues from LLM
        result_dict = normalize_enum_values(result_dict)
        
        log("Chunk extraction completed successfully")
        return result_dict
