"""
Pipeline Orchestration Module

End-to-end pipeline for processing PDFs through OCR and JSON extraction.
"""

import json
from typing import Type, TypeVar

from pydantic import BaseModel

from .pdf_processor import pdf_to_images
from .ocr_engine import extract_text
from .json_extractor import extract_to_json

T = TypeVar("T", bound=BaseModel)


def load_template(template_path: str) -> dict:
    """Load a JSON template from file."""
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)

def process_pdf(
    pdf_path: str,
    pydantic_model: Type[T],
    openai_api_key: str,
    template_path: str | None = None,
    use_grounding: bool = False,
    openai_model: str = "gpt-5.1",
    output_path: str | None = None
) -> T:
    """
    Process a PDF through the full OCR and JSON extraction pipeline.

    Args:
        pdf_path: Path to the input PDF file
        pydantic_model: Pydantic model class for output schema
        openai_api_key: OpenAI API key for JSON extraction
        template_path: Optional path to JSON template for context
        use_grounding: Use grounding mode for OCR (markdown output)
        openai_model: OpenAI model for JSON extraction
        output_path: Optional path to save the extracted JSON output

    Returns:
        Validated Pydantic model instance with extracted data
    """
    # 1. Convert PDF to images
    images = pdf_to_images(pdf_path)
    print(f"Converted PDF to {len(images)} image(s)")

    # 2. Run OCR
    print("Running OCR...")
    ocr_text = extract_text(images, use_grounding=use_grounding)
    print(f"Extracted {len(ocr_text)} characters")

    # 3. Load template context if provided
    template_context = load_template(template_path) if template_path else None

    # 4. Extract structured JSON via OpenAI
    print("Extracting structured JSON...")
    result = extract_to_json(
        ocr_text=ocr_text,
        pydantic_model=pydantic_model,
        api_key=openai_api_key,
        template_context=template_context,
        model=openai_model,
        output_path=output_path
    )

    return result
