"""
Deepseek Service Implementation.

Two-step pipeline:
1. OCR using Ollama (DeepSeek OCR model) to extract text from images
2. JSON extraction using OpenAI to convert OCR text to structured data
"""

import json
import os
import tempfile
from pathlib import Path
from typing import TypeVar

import httpx
import ollama
from dotenv import load_dotenv
from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from PIL import Image
from pydantic import BaseModel

from src.config.loader import DeepseekConfig, ModelConfig
from src.schemas.inspection import InspectionTemplate
from src.utils.logger import log, log_usage
from src.utils.prompts import OCR_EXTRACTION_PROMPT

# Load environment variables from .env file
load_dotenv()

T = TypeVar("T", bound=BaseModel)


# OCR Prompt for DeepSeek
OCR_PROMPT_GROUNDING = "<|grounding|>Convert the document to markdown."
OCR_PROMPT_FREE = "Free OCR."


class OCRError(Exception):
    """Base exception for OCR-related errors."""


class OCRConnectionError(OCRError):
    """Raised when unable to connect to Ollama."""


class OCRModelError(OCRError):
    """Raised when the OCR model is not available or fails."""


class OCRProcessingError(OCRError):
    """Raised when image processing fails."""


class OCRTimeoutError(OCRError):
    """Raised when OCR processing times out."""


class DeepseekService:
    """
    Deepseek implementation of JsonExtractionService.
    
    Two-step pipeline:
    1. OCR via Ollama (DeepSeek OCR)
    2. JSON extraction via OpenAI
    """
    
    def __init__(
        self,
        config: DeepseekConfig | None = None,
        model_config: ModelConfig | None = None,
    ):
        """
        Initialize DeepseekService with configuration.
        
        Args:
            config: DeepseekConfig instance. Uses defaults if not provided.
            model_config: ModelConfig with model_id (OCR model) and supporting_model_id (JSON model).
                         If not provided, uses first model from config or defaults.
        """
        self.config = config or DeepseekConfig()
        
        # Determine which models to use
        if model_config is not None:
            self.ocr_model = model_config.model_id
            self.json_model = model_config.supporting_model_id or "gpt-5.1"
        elif self.config.models:
            first_model = self.config.models[0]
            self.ocr_model = first_model.model_id
            self.json_model = first_model.supporting_model_id or "gpt-5.1"
        else:
            # Fallback defaults
            self.ocr_model = "deepseek-ocr"
            self.json_model = "gpt-5.1"
        
        self._openai_client = None
    
    def _get_openai_client(self) -> OpenAI:
        """Get or create the OpenAI client."""
        if self._openai_client is None:
            api_key = os.getenv("OPENAI_API_KEY")
            self._openai_client = OpenAI(api_key=api_key)
        return self._openai_client
    
    def _process_single_image_ocr(
        self,
        image: Image.Image,
        page_num: int = 1,
    ) -> str:
        """Process a single image through OCR."""
        prompt = OCR_PROMPT_GROUNDING if self.config.use_grounding else OCR_PROMPT_FREE
        
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                image.save(tmp.name, format="PNG")
                tmp_path = tmp.name
        except Exception as e:
            log(f"Failed to save image to temp file: {e}")
            raise OCRProcessingError(f"Failed to save image to temporary file: {e}") from e
        
        try:
            # Create client with timeout
            client = ollama.Client(timeout=self.config.ocr_timeout)
            response = client.chat(
                model=self.ocr_model,
                messages=[{
                    "role": "user",
                    "content": prompt,
                    "images": [tmp_path]
                }]
            )
            
            # Log token usage from Ollama response
            input_tokens = response.get("prompt_eval_count", 0)
            output_tokens = response.get("eval_count", 0)
            
            log_usage(
                provider="ollama",
                model=self.ocr_model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                operation=f"ocr_page_{page_num}"
            )
            
            return response["message"]["content"]
        except ollama.ResponseError as e:
            log(f"Ollama model error: {e}")
            raise OCRModelError(f"OCR model '{self.ocr_model}' error: {e}") from e
        except (httpx.TimeoutException, TimeoutError) as e:
            log(f"OCR timed out after {self.config.ocr_timeout}s on page {page_num}")
            raise OCRTimeoutError(
                f"OCR processing timed out after {self.config.ocr_timeout}s on page {page_num}."
            ) from e
        except (httpx.ConnectError, ConnectionError) as e:
            log(f"Failed to connect to Ollama: {e}")
            raise OCRConnectionError(
                f"Failed to connect to Ollama. Is Ollama running? Error: {e}"
            ) from e
        except Exception as e:
            error_msg = str(e).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                raise OCRTimeoutError(f"OCR processing timed out on page {page_num}: {e}") from e
            if "connection" in error_msg or "connect" in error_msg or "refused" in error_msg:
                raise OCRConnectionError(f"Failed to connect to Ollama: {e}") from e
            log(f"OCR processing error: {e}")
            raise OCRProcessingError(f"OCR processing failed: {e}") from e
        finally:
            Path(tmp_path).unlink(missing_ok=True)
    
    def _extract_text(self, images: list[Image.Image]) -> str:
        """Extract text from images using OCR."""
        log(f"Extracting text from {len(images)} images using {self.ocr_model}")
        
        if not images:
            raise OCRProcessingError("No images provided for OCR processing")
        
        results = []
        failed_pages = []
        total_pages = len(images)
        
        for i, img in enumerate(images):
            page_num = i + 1
            log(f"Processing page {page_num}/{total_pages}...")
            try:
                text = self._process_single_image_ocr(img, page_num=page_num)
                log(f"Completed page {page_num}/{total_pages}")
                results.append(f"[PAGE {page_num}]\n{text}")
            except OCRTimeoutError:
                # If grounding was enabled and timed out, retry without grounding
                if self.config.use_grounding:
                    log(f"Timeout with grounding on page {page_num}, retrying without grounding...")
                    try:
                        # Temporarily disable grounding for retry
                        original_grounding = self.config.use_grounding
                        self.config.use_grounding = False
                        text = self._process_single_image_ocr(img, page_num=page_num)
                        self.config.use_grounding = original_grounding
                        log(f"Completed page {page_num}/{total_pages} (without grounding)")
                        results.append(f"[PAGE {page_num}]\n{text}")
                    except Exception as retry_e:
                        log(f"Failed page {page_num} after retry, skipping: {retry_e}")
                        failed_pages.append(page_num)
                        results.append(f"[PAGE {page_num}]\n[OCR FAILED: {retry_e}]")
                else:
                    log(f"Timeout on page {page_num} without grounding, skipping")
                    failed_pages.append(page_num)
                    results.append(f"[PAGE {page_num}]\n[OCR FAILED: Timeout]")
            except Exception as e:
                log(f"Error processing page {page_num}, skipping: {e}")
                failed_pages.append(page_num)
                results.append(f"[PAGE {page_num}]\n[OCR FAILED: {e}]")
        
        if failed_pages:
            log(f"OCR completed with {len(failed_pages)} failed page(s): {failed_pages}")
        
        return "\n\n".join(results)
    
    def _fix_schema_for_openai(self, schema: dict) -> dict:
        """
        Recursively fix schema for OpenAI strict mode:
        1. Add additionalProperties: false to all objects
        2. Ensure all properties are in the required array
        3. Remove 'default' from properties with '$ref' (not allowed in strict mode)
        """
        if isinstance(schema, dict):
            # OpenAI strict mode: $ref cannot have additional keywords like 'default'
            if "$ref" in schema and "default" in schema:
                del schema["default"]

            # If this is an object with properties, fix it
            if "properties" in schema:
                schema["additionalProperties"] = False
                # OpenAI strict mode requires ALL properties to be in required
                schema["required"] = list(schema["properties"].keys())

            # Process all nested dictionaries
            for value in schema.values():
                if isinstance(value, dict):
                    self._fix_schema_for_openai(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            self._fix_schema_for_openai(item)

            # Process $defs (Pydantic's definitions)
            if "$defs" in schema:
                for def_schema in schema["$defs"].values():
                    self._fix_schema_for_openai(def_schema)

        return schema
    
    def _extract_json(
        self,
        ocr_text: str,
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """Extract structured JSON from OCR text using OpenAI."""
        log(f"Extracting JSON using OpenAI [{self.json_model}]")
        
        client = self._get_openai_client()
        
        # Generate and fix schema for OpenAI strict mode
        json_schema = schema.model_json_schema()
        json_schema = self._fix_schema_for_openai(json_schema)
        
        prompt = OCR_EXTRACTION_PROMPT.format(
            ocr_text=ocr_text,
            template_context=json.dumps(context, indent=2) if context else "N/A"
        )
        
        response = client.chat.completions.create(
            model=self.json_model,
            messages=[
                ChatCompletionSystemMessageParam(
                    role="system",
                    content="You are a precise document parser. Extract data according to the schema."
                ),
                ChatCompletionUserMessageParam(
                    role="user",
                    content=prompt
                )
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": schema.__name__,
                    "strict": True,
                    "schema": json_schema
                }
            },
            temperature=self.config.json_temperature
        )
        
        # Log OpenAI token usage
        if response.usage:
            log_usage(
                provider="openai",
                model=self.json_model,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
                operation="json_extraction"
            )
        
        result_text = response.choices[0].message.content
        result_dict = json.loads(result_text) if result_text else {}

        return result_dict
    
    def generate_json(
        self,
        images: list[Image.Image],
        schema: type[T],
        context: dict | None = None,
    ) -> T:
        """
        Generate structured JSON from images using two-step pipeline.
        
        Step 1: OCR via Ollama (DeepSeek OCR)
        Step 2: JSON extraction via OpenAI
        
        Args:
            images: List of PIL Images (one per page)
            schema: Pydantic model class for the output schema
            context: Optional template dictionary for additional context
            
        Returns:
            Validated Pydantic model instance with extracted data
        """
        log(f"Starting Deepseek pipeline for {len(images)} image(s)")
        log(f"OCR Model: {self.ocr_model}, JSON Model: {self.json_model}")
        
        # Step 1: OCR
        log("Step 1: Running OCR...")
        ocr_text = self._extract_text(images)
        log(f"OCR completed: {len(ocr_text)} characters extracted")
        
        # Step 2: JSON extraction
        log("Step 2: Extracting structured JSON...")
        result = self._extract_json(ocr_text, schema, context)
        
        log("Deepseek pipeline completed successfully")
        return result
