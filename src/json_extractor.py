"""
JSON Extraction Module

Uses OpenAI to convert OCR text into structured JSON using Pydantic schema.
"""

import json
from pathlib import Path
from typing import Type, TypeVar

from openai import OpenAI
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam
from pydantic import BaseModel

from .usage_logger import log, log_openai_usage

T = TypeVar("T", bound=BaseModel)


EXTRACTION_PROMPT = """You are an inspection template parser. Given OCR-extracted text from an inspection form, extract ONLY the inspection template structure (rooms/areas with their inspection fields).

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
The template must follow this hierarchy:
1. **SECTION_DISPLAY_TYPE_UNSPECIFIED**: Root section containing TABs (has child sections, NO fields)
2. **SECTION_DISPLAY_TYPE_TAB**: Contains ACCORDIONs (has child sections, NO fields)
3. **SECTION_DISPLAY_TYPE_ACCORDION**: Contains FIELD_SETs (has child sections, NO fields)
4. **SECTION_DISPLAY_TYPE_FIELD_SET**: Leaf node containing fields (has fields, NO child sections)

## Field Rating Types (REQUIRED - never use UNSPECIFIED)
- **RATING_TYPE_CHECKBOX**: For multi-select options (can select multiple)
- **RATING_TYPE_RADIO**: For single-select options (select exactly one) - USE THIS FOR MOST INSPECTION FIELDS
- **RATING_TYPE_SELECT**: For dropdown selection

## Field Extraction Rules
- Generate sequential `id` starting from 1
- Extract `name` from the field label in the document
- Set `mandatory` to true for required fields
- Extract `options` as list of FULLY EXPANDED choices (NOT acronyms)
- Set `notes_enabled: true` if the field has a notes/comments area
- Set `attachments_enabled: true` if photos/attachments are mentioned

## Work Order Configuration (IMPORTANT)
Not every field needs a work order. Only set `can_create_work_order: true` for fields where maintenance work might be needed based on the inspection result.

**Rules:**
1. If `can_create_work_order` is FALSE → leave category/subcategory as UNSPECIFIED
2. If `can_create_work_order` is TRUE → you MUST set appropriate category AND subcategory (NOT UNSPECIFIED)
3. Infer the category from the field name and section context:

**Category Mapping (based on field type):**
- Stove, Oven, Refrigerator, Dishwasher, Microwave → APPLIANCE_REPAIR
- Sink, Faucet, Toilet, Shower, Tub, Drain, Water Heater → PLUMBING
- Outlets, Switches, Light Fixtures, Wiring, Circuit Breaker → ELECTRICAL
- AC, Heating, Furnace, Thermostat, Vents → HVAC
- Doors, Windows, Cabinets, Drywall, Trim → CARPENTRY
- Walls (paint), Ceiling (paint), Touch-up → PAINTING
- Floor, Carpet, Tile, Hardwood → FLOORING
- Locks, Security System, Intercom → SECURITY
- Roof, Gutters, Siding, Landscaping → EXTERIOR
- Rodents, Insects, Pests → PEST_CONTROL
- General cleaning items → CLEANING
- Other/misc items → GENERAL

**Subcategory:** Choose the most specific subcategory that matches the field. If unsure, use UNSPECIFIED only when can_create_work_order is false.

## Document Order
- Text is marked with [PAGE N] to indicate page numbers
- Preserve the exact order sections appear in the document

OCR Text:
{ocr_text}

Additional context (example template):
{template_context}

REMEMBER: Find the legend/key FIRST, then expand ALL acronyms to their full names. Extract ONLY inspection template sections with their fields. Do NOT include any header or footer information.
"""


def _fix_schema_for_openai(schema: dict) -> dict:
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
                _fix_schema_for_openai(value)
            elif isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        _fix_schema_for_openai(item)

        # Process $defs (Pydantic's definitions)
        if "$defs" in schema:
            for def_schema in schema["$defs"].values():
                _fix_schema_for_openai(def_schema)

    return schema


def extract_to_json(
    ocr_text: str,
    pydantic_model: Type[T],
    api_key: str,
    template_context: dict | None = None,
    model: str = "gpt-5.1",
    output_path: str | Path | None = None
) -> T:
    """
    Extract structured JSON from OCR text using OpenAI with Pydantic schema.
    
    Args:
        ocr_text: The OCR-extracted text from the document
        pydantic_model: Pydantic model class for the output schema
        api_key: OpenAI API key
        template_context: Optional template dictionary for additional context
        model: OpenAI model to use
        output_path: Optional path to save the extracted JSON output
    
    Returns:
        Validated Pydantic model instance with extracted data
    """
    client = OpenAI(api_key=api_key)

    # Generate and fix schema for OpenAI strict mode
    json_schema = pydantic_model.model_json_schema()
    json_schema = _fix_schema_for_openai(json_schema)

    prompt = EXTRACTION_PROMPT.format(
        ocr_text=ocr_text,
        template_context=json.dumps(template_context, indent=2) if template_context else "N/A"
    )

    response = client.chat.completions.create(
        model=model,
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
                "name": pydantic_model.__name__,
                "strict": True,
                "schema": json_schema
            }
        },
        temperature=0.0
    )

    # Log OpenAI token usage and cost
    if response.usage:
        log_openai_usage(
            model=model,
            input_tokens=response.usage.prompt_tokens,
            output_tokens=response.usage.completion_tokens,
            total_tokens=response.usage.total_tokens,
            operation="json_extraction"
        )

    result_text = response.choices[0].message.content
    result_dict = json.loads(result_text) if result_text else {}

    result = pydantic_model.model_validate(result_dict)

    # Write output to file if path provided
    if output_path:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result.model_dump(), f, indent=2)
        print(f"Output saved to {output_path}")

    return result
