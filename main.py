"""
OCR-AI: PDF to Structured JSON Pipeline
"""

from pathlib import Path
from dotenv import load_dotenv
import os

from src.pipeline import process_pdf
from src.schemas import InspectionTemplate

# Load .env file
load_dotenv()

# Hardcoded config
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
MODEL = "gpt-5.2"


def get_output_path(pdf_path: Path) -> Path:
    """Generate output path from PDF filename: output_{filename}.json"""
    stem = pdf_path.stem  # filename without extension
    return OUTPUT_DIR / f"output_{stem}.json"


def main():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY not found in .env file")
        return

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Find all PDF files in input directory
    pdf_files = list(INPUT_DIR.glob("*.pdf"))
    
    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return
    
    print(f"Found {len(pdf_files)} PDF file(s) to process")
    
    for i, pdf_path in enumerate(pdf_files, 1):
        output_path = get_output_path(pdf_path)
        print(f"\n{'='*60}")
        print(f"[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")
        print(f"Output: {output_path}")
        print('='*60)
        
        try:
            result = process_pdf(
                pdf_path=str(pdf_path),
                pydantic_model=InspectionTemplate,
                openai_api_key=api_key,
                template_path="templates/inspection_template.json",
                use_grounding=True,
                openai_model=MODEL,
                output_path=str(output_path)
            )
            print(f"✓ Successfully processed: {pdf_path.name}")
        except Exception as e:
            print(f"✗ Error processing {pdf_path.name}: {e}")
    
    print(f"\n{'='*60}")
    print(f"Processing complete. {len(pdf_files)} file(s) processed.")


if __name__ == "__main__":
    main()
