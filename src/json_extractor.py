"""
JSON Extraction Module

Uses OpenAI to convert OCR text into structured JSON using Pydantic schema.
"""

import json
from pathlib import Path
from typing import Type, TypeVar

from openai import OpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


EXTRACTION_PROMPT = """You are a document parser. Given the OCR-extracted text from an inspection form, extract the relevant information and populate the JSON structure according to the provided schema.

IMPORTANT: Maintain the exact order of sections as they appear in the document.
- Text is marked with [PAGE N] to indicate page numbers
- If Bathroom appears on page 1 and Kitchen on page 2, the JSON sections array must have Bathroom before Kitchen
- Preserve the document's original ordering throughout the hierarchy

Your task:
1. Read the OCR text carefully, noting page numbers and section order
2. Identify fields that match the schema structure
3. Extract values and populate the JSON IN THE SAME ORDER as the document
4. Use null for any fields where data is not found

OCR Text:
{ocr_text}

Additional context (example template):
{template_context}

Extract the inspection data and return valid JSON matching the schema structure, preserving document order.
"""


def _fix_schema_for_openai(schema: dict) -> dict:
    """
    Recursively fix schema for OpenAI strict mode:
    1. Add additionalProperties: false to all objects
    2. Ensure all properties are in the required array
    """
    if isinstance(schema, dict):
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
            {
                "role": "system",
                "content": "You are a precise document parser. Extract data according to the schema."
            },
            {
                "role": "user",
                "content": prompt
            }
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
