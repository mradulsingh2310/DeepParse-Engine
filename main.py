"""
OCR-AI: PDF to Structured JSON Pipeline
"""

from pathlib import Path

from src.pipeline import process_pdf
from src.schemas import InspectionTemplate
from src.usage_logger import get_tracker, reset_tracker

# Hardcoded config
INPUT_DIR = Path("input")
OUTPUT_DIR = Path("output")
IMG_DIR = Path("img")
BACKEND = "bedrock"  # "bedrock" or "deepseek"


def get_output_path(pdf_path: Path) -> Path:
    """Generate output path from PDF filename: output_{filename}.json"""
    stem = pdf_path.stem  # filename without extension
    return OUTPUT_DIR / f"output_{stem}.json"


def main():
    # Reset usage tracker at start
    reset_tracker()

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Find all PDF files in input directory
    pdf_files = list(INPUT_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"No PDF files found in {INPUT_DIR}")
        return

    print(f"Found {len(pdf_files)} PDF file(s) to process")
    print(f"Using backend: {BACKEND}")

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
                template_path="templates/inspection_template.json",
                output_path=str(output_path),
                save_images_dir=str(IMG_DIR),
                backend=BACKEND,
            )
            print(f"Successfully processed: {pdf_path.name}")
        except Exception as e:
            print(f"Error processing {pdf_path.name}: {e}")

    print(f"\n{'='*60}")
    print(f"Processing complete. {len(pdf_files)} file(s) processed.")

    # Print usage summary
    tracker = get_tracker()
    tracker.print_summary()


if __name__ == "__main__":
    main()
