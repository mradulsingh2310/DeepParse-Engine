"""
OCR-AI: PDF to Structured JSON Benchmarking Pipeline

Main entry point for benchmarking PDF document extraction
across multiple providers and models.
"""

import json
from pathlib import Path

from src.config import Provider, load_config, ModelConfig
from src.config.loader import AppConfig
from src.services import get_service
from src.schemas import InspectionTemplate
from src.utils import pdf_to_images, log, get_tracker, reset_tracker

# Evaluation imports
from evaluation.runner import run_post_extraction_evaluation


def load_template(template_path: str | Path) -> dict:
    """Load a JSON template from file."""
    with open(template_path, "r", encoding="utf-8") as f:
        return json.load(f)


def sanitize_name(name: str) -> str:
    """Sanitize name for use in file paths."""
    return name.replace(".", "_").replace("/", "_").replace(":", "_")


def get_model_display_name(model_config: ModelConfig) -> str:
    """Get a display name for the model configuration."""
    if model_config.supporting_model_id:
        return f"{model_config.model_id}+{model_config.supporting_model_id}"
    return model_config.model_id


def get_output_path(
    base_output_dir: Path,
    provider: Provider,
    model_config: ModelConfig,
    pdf_stem: str,
) -> Path:
    """
    Generate output path with provider/model directory structure.
    
    Structure: output/{provider}/{model}/{pdf_stem}.json
    """
    provider_name = sanitize_name(provider.value)
    model_name = sanitize_name(get_model_display_name(model_config))
    
    return base_output_dir / provider_name / model_name / f"{pdf_stem}.json"


def save_result(
    result: InspectionTemplate | dict,
    output_path: Path,
    provider: Provider,
    model_config: ModelConfig,
) -> None:
    """Save extraction result to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Handle both dict and Pydantic model results
    result_dict = result if isinstance(result, dict) else result.model_dump()
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, indent=2)
    
    log(f"Output saved to {output_path}")


def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    provider: Provider,
    model_config: ModelConfig,
    config: AppConfig,
    template_path: Path | None = None,
    save_images_dir: Path | None = None,
    images: list | None = None,
) -> InspectionTemplate | dict:
    """
    Process a PDF through the extraction pipeline.
    
    Args:
        pdf_path: Path to the input PDF file
        output_dir: Base directory to save the output JSON
        provider: Provider to use
        model_config: Model configuration to use
        config: App configuration
        template_path: Optional path to context template JSON
        save_images_dir: Optional directory to save converted images
        images: Pre-converted images (to avoid re-converting for each model)
        
    Returns:
        Extracted InspectionTemplate
    """
    model_display = get_model_display_name(model_config)
    service = get_service(provider, config, model_config)
    
    log(f"Processing: {pdf_path.name}")
    log(f"Provider: {provider.value}, Model: {model_display}")
    
    # Convert PDF to images if not provided
    if images is None:
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
    
    # Generate output path with provider/model directory structure
    output_path = get_output_path(output_dir, provider, model_config, pdf_path.stem)
    
    # Save result
    save_result(result, output_path, provider, model_config)
    
    return result


def get_provider_models(provider: Provider, config: AppConfig) -> list[ModelConfig]:
    """Get the list of models configured for a provider."""
    match provider:
        case Provider.BEDROCK:
            return config.providers.bedrock.models
        case Provider.DEEPSEEK:
            return config.providers.deepseek.models
        case Provider.GOOGLE:
            return config.providers.google.models
        case Provider.ANTHROPIC:
            return config.providers.anthropic.models
        case _:
            return []


def run_benchmark(
    pdf_files: list[Path],
    output_dir: Path,
    config: AppConfig,
    template_path: Path | None = None,
    images_dir: Path | None = None,
) -> None:
    """
    Run benchmark across all configured providers and models.
    
    Args:
        pdf_files: List of PDF files to process
        output_dir: Base output directory
        config: App configuration
        template_path: Optional template path for context
        images_dir: Optional directory to save images
    """
    # Collect all provider/model combinations
    benchmark_configs: list[tuple[Provider, ModelConfig]] = []
    
    for provider in Provider:
        models = get_provider_models(provider, config)
        for model_config in models:
            benchmark_configs.append((provider, model_config))
    
    if not benchmark_configs:
        log("No models configured for benchmarking. Check your config.yaml")
        return
    
    total_runs = len(benchmark_configs) * len(pdf_files)
    log("Benchmark Configuration:")
    log(f"  - Providers/Models: {len(benchmark_configs)}")
    log(f"  - PDF Files: {len(pdf_files)}")
    log(f"  - Total Runs: {total_runs}")
    log("")
    
    # List all configured models
    for provider, model_config in benchmark_configs:
        model_display = get_model_display_name(model_config)
        log(f"  [{provider.value}] {model_display}")
    log("")
    
    run_count = 0
    
    # Process each PDF file
    for pdf_path in pdf_files:
        log("=" * 70)
        log(f"PDF: {pdf_path.name}")
        log("=" * 70)
        
        # Convert PDF to images once per PDF (reuse across models)
        images = pdf_to_images(pdf_path, save_dir=images_dir)
        log(f"Converted PDF to {len(images)} image(s)")
        
        # Run extraction for each provider/model combination
        for provider, model_config in benchmark_configs:
            run_count += 1
            model_display = get_model_display_name(model_config)
            
            log("-" * 70)
            log(f"[{run_count}/{total_runs}] {provider.value} / {model_display}")
            log("-" * 70)
            
            try:
                process_pdf(
                    pdf_path=pdf_path,
                    output_dir=output_dir,
                    provider=provider,
                    model_config=model_config,
                    config=config,
                    template_path=template_path,
                    images=images,  # Reuse converted images
                )
                log(f"SUCCESS: {pdf_path.name} with {provider.value}/{model_display}")
            except Exception as e:
                log(f"ERROR: {pdf_path.name} with {provider.value}/{model_display}: {e}")
        
        log("")


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
    
    log(f"Found {len(pdf_files)} PDF file(s) to process")
    log("")
    
    # Run the benchmark
    run_benchmark(
        pdf_files=pdf_files,
        output_dir=output_dir,
        config=config,
        template_path=template_path if template_path.exists() else None,
        images_dir=images_dir,
    )
    
    # Print usage summary
    log("=" * 70)
    log("Benchmark Complete")
    log("=" * 70)
    tracker = get_tracker()
    tracker.print_summary()

    # Convert tracker data to usage_data format for evaluation
    # Format: {"{provider}:{model_id}": {"cost": float, "input_tokens": int, "output_tokens": int}}
    usage_data: dict[str, dict] = {}
    for record in tracker.records:
        key = f"{record.provider}:{record.model}"
        if key not in usage_data:
            usage_data[key] = {"cost": 0.0, "input_tokens": 0, "output_tokens": 0}
        usage_data[key]["cost"] += record.cost_usd
        usage_data[key]["input_tokens"] += record.input_tokens
        usage_data[key]["output_tokens"] += record.output_tokens

    # Run automatic evaluation
    run_post_extraction_evaluation(
        output_dir=output_dir,
        source_of_truth_dir=Path("source_of_truth"),
        cache_dir=Path("evaluation_results"),
        usage_data=usage_data,
        quiet=False,
    )


if __name__ == "__main__":
    main()
