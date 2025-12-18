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
from src.utils.prompts import VISION_EXTRACTION_PROMPT

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
        
        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context
            
        Returns:
            Validated Pydantic model instance with extracted data
        """
        log(f"Extracting JSON from {len(images)} image(s) using Bedrock [{self.model_id}]")
        
        client = self._get_client()
        
        # Generate JSON schema from Pydantic model
        json_schema = schema.model_json_schema()
        
        # Get enum values as strings for the prompt
        maintenance_categories = [cat.value for cat in MaintenanceCategory]
        work_order_subcategories = [sub.value for sub in WorkOrderSubCategory]
        
        # Build the prompt
        prompt = VISION_EXTRACTION_PROMPT.format(
            json_schema=json.dumps(json_schema, indent=2),
            template_context=json.dumps(context, indent=2) if context else "N/A",
            maintenance_categories=json.dumps(maintenance_categories, indent=2),
            work_order_subcategories=json.dumps(work_order_subcategories, indent=2)
        )
        
        # Build content blocks: text prompt first, then all images
        content: list[dict] = [{"text": prompt}]
        
        for i, img in enumerate(images):
            log(f"Adding image {i + 1}/{len(images)} to request...")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            
            content.append({
                "image": {
                    "format": "png",
                    "source": {"bytes": image_bytes}
                }
            })
        
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
        
        log("Raw response from Bedrock (normalized):")
        return result_dict
