"""
OCR-AI: PDF to Structured JSON Pipeline

Main entry point for processing PDF documents and extracting
structured JSON using AI-powered extraction.
"""

import json
from pathlib import Path

from src.config import Provider, load_config
from src.config.loader import AppConfig
from src.services import get_service
from src.schemas import InspectionTemplate
from src.utils import pdf_to_images, log, get_tracker, reset_tracker


def load_template(template_path: str | Path) -> dict:
    """Load a JSON template from file."""
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_name(name: str) -> str:
    """Sanitize name for use in file paths."""
    return name.replace(".", "_").replace("/", "_").replace(":", "_")


def get_model_name(provider: Provider, config: AppConfig) -> str:
    """Get the model name for a given provider from config."""
    match provider:
        case Provider.BEDROCK:
            return config.providers.bedrock.model_id
        case Provider.DEEPSEEK:
            return config.providers.deepseek.json_model
        case _:
            return "unknown"


def get_output_filename(pdf_stem: str, provider: Provider, model: str) -> str:
    """Generate output filename with provider and model info."""
    provider_name = sanitize_name(provider.value)
    model_name = sanitize_name(model)
    return f"{pdf_stem}_{provider_name}_{model_name}.json"


def save_result(
    result: InspectionTemplate,
    output_path: Path,
    provider: Provider,
    model: str,
) -> None:
    """Save extraction result to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    output_data = {
        "_metadata": {
            "provider": provider.value,
            "model": model,
        },
        **result.model_dump(),
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)
    
    log(f"Output saved to {output_path}")


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    provider: Provider | None = None,
    template_path: Path | None = None,
    save_images_dir: Path | None = None,
) -> InspectionTemplate:
    """
    Process a PDF through the extraction pipeline.
    
    Args:
        pdf_path: Path to the input PDF file
        output_dir: Directory to save the output JSON
        provider: Provider to use. Uses config default if not specified.
        template_path: Optional path to context template JSON
        save_images_dir: Optional directory to save converted images
        
    Returns:
        Extracted InspectionTemplate
    """
    # Load config and get service
    config = load_config()
    provider = provider or config.default_provider
    model = get_model_name(provider, config)
    service = get_service(provider, config)
    
    log(f"Processing: {pdf_path.name}")
    log(f"Provider: {provider.value}, Model: {model}")
    
    # Convert PDF to images
    images = pdf_to_images(
        pdf_path,
        save_dir=save_images_dir
    )
    log(f"Converted PDF to {len(images)} image(s)")
    
    # Load template context if provided
    context = load_template(template_path) if template_path else None
    
    # Extract JSON using the service
    result = service.generate_json(
        images=images,
        schema=InspectionTemplate,
        context=context,
    )
    
    # Generate output path with provider and model in filename
    output_filename = get_output_filename(pdf_path.stem, provider, model)
    output_path = output_dir / output_filename
    
    # Save result
    save_result(result, output_path, provider, model)
    
    return result


def main():
    """Main entry point."""
    # Reset usage tracker
    reset_tracker()
    
    # Configuration
    config = load_config()
    input_dir = Path("input")
    output_dir = Path(config.output.output_dir)
    images_dir = Path(config.output.images_dir) if config.output.save_images else None
    template_path = Path("templates/inspection_template.json")
    
    # Ensure directories exist
    output_dir.mkdir(exist_ok=True)
    
    # Find all PDF files
    pdf_files = list(input_dir.glob("*.pdf"))
    
    if not pdf_files:
        log(f"No PDF files found in {input_dir}")
        return
    
    provider = config.default_provider
    model = get_model_name(provider, config)
    
    log(f"Found {len(pdf_files)} PDF file(s) to process")
    log(f"Using provider: {provider.value}, model: {model}")
    
    # Process each PDF
    for i, pdf_path in enumerate(pdf_files, 1):
        log("=" * 60)
        log(f"[{i}/{len(pdf_files)}] {pdf_path.name}")
        log("=" * 60)
        
        try:
            process_pdf(
                pdf_path=pdf_path,
                output_dir=output_dir,
                template_path=template_path if template_path.exists() else None,
                save_images_dir=images_dir,
            )
            log(f"Successfully processed: {pdf_path.name}")
        except Exception as e:
            log(f"Error processing {pdf_path.name}: {e}")
    
    # Print usage summary
    log("=" * 60)
    log(f"Processing complete. {len(pdf_files)} file(s) processed.")
    get_tracker().print_summary()


if __name__ == "__main__":
    main()
