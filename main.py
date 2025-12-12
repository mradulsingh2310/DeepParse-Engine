"""
OCR-AI: PDF to Structured JSON Pipeline
"""

import json
from dotenv import load_dotenv
import os

from src.pipeline import process_pdf
from src.schemas import InspectionTemplate

# Load .env file
load_dotenv()

# Hardcoded config
PDF_PATH = "input/11_HQS_Inspection_Form.pdf"
OUTPUT_PATH = "output/inspection_result.json"
MODEL = "gpt-5.1"


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in .env file")
        return

    result = process_pdf(
        pdf_path=PDF_PATH,
        pydantic_model=InspectionTemplate,
        openai_api_key=api_key,
        template_path="templates/inspection_template.json",
        use_grounding=True,
        openai_model=MODEL,
        output_path=OUTPUT_PATH
    )

    print(json.dumps(result.model_dump(), indent=2))


if __name__ == "__main__":
    main()
