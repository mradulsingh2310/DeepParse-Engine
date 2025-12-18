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

# Load environment variables from .env file
load_dotenv()

T = TypeVar("T", bound=BaseModel)


EXTRACTION_PROMPT = """You are an inspection template parser. Given images of an inspection form, extract ONLY the inspection template structure (rooms/areas with their inspection fields).

## CRITICAL: What to EXCLUDE (DO NOT extract these)
- **Header information**: Project name, owner name, inspector name, date of inspection, inspection type, property address, unit number, or any metadata about the inspection itself
- **Footer information**: Comments section, inspector's signature, tenant's signature, date fields, certification statements, any sign-off sections
- **Non-inspection content**: Instructions, legends, form numbers, page numbers

## CRITICAL: What to INCLUDE (ONLY extract these)
- **Inspection sections**: Rooms/areas like Kitchen, Bathroom, Living Room, Bedroom, etc.
- **Inspection fields**: Individual items to inspect within each section (e.g., "Stove/Range", "Refrigerator", "Sink", "Ceiling", "Walls", "Floor")
- **Field options**: The rating options available for each field (e.g., "Pass", "Fail", "Inconclusive", "N/A")

## CRITICAL: Acronym/Abbreviation Expansion
IMPORTANT: Many inspection forms use acronyms or abbreviations with a legend/key explaining their meanings.
1. **FIRST**: Search the ENTIRE document for any legend, key, or abbreviation table (often at top, bottom, or in headers)
   - Look for patterns like: "G = Good", "P = Pass", "F = Fail", "Inc = Inconclusive", "NA = Not Applicable"
   - Look for rating scales like: "1 = Poor, 2 = Fair, 3 = Good, 4 = Excellent"
2. **THEN**: When extracting field options, ALWAYS use the FULL expanded name, NOT the acronym
   - If legend says "G = Good", use "Good" in options, NOT "G"
   - If legend says "Pass/Fail/Inc/NA", expand to ["Pass", "Fail", "Inconclusive", "Not Applicable"]
   - If legend says "Y/N", expand to ["Yes", "No"]
3. **Common abbreviations to expand**:
   - G → Good, B -> Bad
   - Y → Yes, N → No, NA/N/A → Not Applicable
   - Inc → Inconclusive, Sat → Satisfactory, Unsat → Unsatisfactory
   - OK → Okay/Acceptable, NI → Needs Improvement

## Section Hierarchy Rules
The template must follow a hierarchy using the `SectionDisplayType` enum values from the schema:

**Available Display Types:**
- **SECTION_DISPLAY_TYPE_UNSPECIFIED**: Root/parent section (contains child sections, NO fields directly)
- **SECTION_DISPLAY_TYPE_ACCORDION**: Collapsible section for grouping related items (can contain FIELD_SETs or other sections)
- **SECTION_DISPLAY_TYPE_FIELD_SET**: Leaf node containing actual inspection fields (has fields, NO child sections)

**Hierarchy Examples:**
1. Root (UNSPECIFIED) → Accordions (ACCORDION) → Field Sets (FIELD_SET) with fields
2. Root (UNSPECIFIED) → Sections (UNSPECIFIED) → Field Sets (FIELD_SET) with fields
3. Root (UNSPECIFIED) → Field Sets (FIELD_SET) directly (for simple forms)

**Key Rules:**
- FIELD_SET is ALWAYS a leaf node - it contains fields and has NO child sections
- FIELD_SET can be nested within any parent: root, accordion, or other sections
- ACCORDIONs are for visually collapsible groups (like room categories)
- Use UNSPECIFIED for intermediate grouping sections that aren't collapsible
**IMPORTANT:** Use ONLY the display type values defined in the schema's `SectionDisplayType` enum. Do NOT use TAB - it is not a valid type.

## Field Rating Types
Choose rating types ONLY from the `RatingType` enum values in the schema:
- Use CHECKBOX type for multi-select options (can select multiple)
- Use RADIO type for single-select options (select exactly one) - USE THIS FOR MOST INSPECTION FIELDS
- Use SELECT type for dropdown selection
**IMPORTANT:** Never use UNSPECIFIED for rating_type. Pick the most appropriate type from the schema.

## Field Extraction Rules
- Generate sequential `id` starting from 1
- Extract `name` from the field label in the document
- Set `mandatory` to true for required fields
- Extract `options` as list of FULLY EXPANDED choices (NOT acronyms)
- Set `notes_enabled: true` if the field has a notes/comments area
- Set `attachments_enabled: true` if photos/attachments are mentioned
- **IMPORTANT:** For ALL enum fields, use ONLY values defined in the schema. Do not invent new values.

## Work Order Configuration (IMPORTANT)
Not every field needs a work order. Only set `can_create_work_order: true` for fields where maintenance work might be needed based on the inspection result.

**Rules:**
1. If `can_create_work_order` is FALSE → leave category/subcategory as UNSPECIFIED
2. If `can_create_work_order` is TRUE → you MUST set appropriate category AND subcategory (NOT UNSPECIFIED)
3. **CRITICAL:** You MUST use EXACTLY these enum values. Do NOT modify, shorten, or invent new values.
4. Infer the most appropriate category from the field name and section context.

**ALLOWED MaintenanceCategory values (use EXACTLY as written):**
{maintenance_categories}

**ALLOWED WorkOrderSubCategory values (use EXACTLY as written):**
{work_order_subcategories}

## Image Order
- Images are provided in page order (image 1 = page 1, image 2 = page 2, etc.)
- Preserve the exact order sections appear in the document

## Output Format
Output valid JSON matching this schema:
{json_schema}

Additional context (example template):
{template_context}

## CRITICAL OUTPUT RULES
1. **NEVER truncate or abbreviate the output** - output the COMPLETE JSON for ALL fields and sections
2. **NEVER use placeholders** like "...", "etc.", or similar abbreviations in the JSON output
3. **Output valid JSON only** - ensure all brackets, quotes, and commas are properly formatted
4. If the form has many fields, output ALL of them completely - do not skip or summarize

REMEMBER: Find the legend/key FIRST, then expand ALL acronyms to their full names. Extract ONLY inspection template sections with their fields. Do NOT include any header or footer information.
"""


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
        
        # Determine which model to use
        if model_config is not None:
            self.model_id = model_config.model_id
        elif self.config.models:
            self.model_id = self.config.models[0].model_id
        else:
            # Fallback default
            self.model_id = "qwen.qwen3-vl-235b-a22b"
        
        self._client = None
    
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
        prompt = EXTRACTION_PROMPT.format(
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
                    "maxTokens": self.config.max_tokens,
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
        
        # Always log the raw response for debugging
        log("Raw response from Bedrock (normalized):")
        print(json.dumps(result_dict, indent=2))
        log("Extraction completed successfully")
        return result_dict
