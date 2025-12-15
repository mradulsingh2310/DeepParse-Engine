"""
Pipeline Orchestration Module

End-to-end pipeline for processing PDFs through OCR and JSON extraction.
Supports two backends:
- "bedrock": Single request using AWS Bedrock - images directly to JSON
- "deepseek": Two-step using DeepSeek OCR + OpenAI for JSON extraction
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, Type, TypeVar

from pydantic import BaseModel

from .pdf_processor import pdf_to_images
from .ocr_engine import extract_text
from .json_extractor import extract_to_json
from .bedrock_extractor import extract_to_json_from_images

T = TypeVar("T", bound=BaseModel)

Backend = Literal["bedrock", "deepseek"]


def load_template(template_path: str) -> dict:
    """Load a JSON template from file."""
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_with_metadata(result: BaseModel, backend: Backend, output_path: str) -> None:
    """Save result JSON with metadata about the backend used."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "_metadata": {
            "backend": backend,
            "model": "qwen.qwen3-vl-235b-a22b" if backend == "bedrock" else "deepseek-ocr + gpt-5.1",
            "generated_at": datetime.now().isoformat(),
        },
        **result.model_dump(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    print(f"Output saved to {output_path}")


def process_pdf(
    pdf_path: str,
    pydantic_model: Type[T],
    template_path: str | None = None,
    use_grounding: bool = False,
    openai_model: str = "gpt-5.1",
    output_path: str | None = None,
    save_images_dir: str | None = None,
    backend: Backend = "bedrock",
) -> T:
    """
    Process a PDF through the full extraction pipeline.

    Args:
        pdf_path: Path to the input PDF file
        pydantic_model: Pydantic model class for output schema
        openai_api_key: OpenAI API key (required for deepseek backend)
        template_path: Optional path to JSON template for context
        use_grounding: Use grounding mode for OCR (deepseek backend only)
        openai_model: OpenAI model for JSON extraction (deepseek backend only)
        output_path: Optional path to save the extracted JSON output
        save_images_dir: Optional directory to save converted images
        backend: "bedrock" (default) or "deepseek"

    Returns:
        Validated Pydantic model instance with extracted data
    """
    # 1. Convert PDF to images
    images = pdf_to_images(pdf_path, save_dir=save_images_dir)
    print(f"Converted PDF to {len(images)} image(s)")

    # 2. Load template context if provided
    template_context = load_template(template_path) if template_path else None

    if backend == "bedrock":
        # Single request: images -> JSON via Bedrock
        print("Extracting JSON using Bedrock...")
        result = extract_to_json_from_images(
            images=images,
            pydantic_model=pydantic_model,
            template_context=template_context,
        )
    else:
        # Two-step: images -> OCR -> JSON via DeepSeek + OpenAI
        print("Running OCR...")
        ocr_text = extract_text(images, use_grounding=use_grounding)
        print(f"Extracted {len(ocr_text)} characters")

        print("Extracting structured JSON...")
        result = extract_to_json(
            ocr_text=ocr_text,
            pydantic_model=pydantic_model,
            template_context=template_context,
            model=openai_model,
        )

    # Save with metadata
    if output_path:
        save_with_metadata(result, backend, output_path)

    return result
