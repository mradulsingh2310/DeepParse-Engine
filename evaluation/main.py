"""
Evaluation CLI Entry Point

Provides command-line interface for evaluating model outputs against source of truth.
"""

from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

from evaluation.models import (
    EvaluationResult,
    ComparisonReport,
    ModelMetadata,
)
from evaluation.schema_validator import validate_schema
from evaluation.field_comparator import (
    load_json_file,
    compare_templates,
    extract_sections,
)
from evaluation.llm_evaluator import (
    LLMEvaluator,
    update_evaluations_with_llm_scores,
)
from evaluation.scorer import (
    score_all_fields,
    calculate_aggregate_scores,
)
from evaluation.visualizer import generate_all_charts
from evaluation.report import (
    generate_json_report,
    generate_console_report,
    generate_html_report,
)
from evaluation.cache import (
    load_cache,
    update_cache_with_results,
)

from src.utils.logger import log


def find_model_outputs(output_dir: Path, source_filename: str) -> list[Path]:
    """
    Find all model output files that match the source filename.
    
    Searches for files containing the source filename in various subdirectories.
    """
    source_stem = Path(source_filename).stem
    model_files = []
    
    # Search patterns
    patterns = [
        f"*{source_stem}*.json",
        f"**/*{source_stem}*.json",
    ]
    
    for pattern in patterns:
        for path in output_dir.glob(pattern):
            # Skip source of truth files
            if "source_of_truth" in str(path):
                continue
            if path.is_file():
                model_files.append(path)
    
    # Remove duplicates
    return list(set(model_files))


def extract_metadata(json_data: dict, file_path: Path) -> ModelMetadata:
    """Extract model metadata from JSON or filename."""
    metadata = json_data.get("_metadata", {})
    
    if metadata:
        return ModelMetadata(
            provider=metadata.get("provider", "unknown"),
            model_id=metadata.get("model_id", file_path.stem),
            supporting_model_id=metadata.get("supporting_model_id"),
        )
    
    # Infer from filename
    filename = file_path.stem.lower()
    
    if "bedrock" in filename:
        provider = "bedrock"
    elif "deepseek" in filename:
        provider = "deepseek"
    elif "openai" in filename:
        provider = "openai"
    else:
        provider = "unknown"
    
    return ModelMetadata(
        provider=provider,
        model_id=file_path.stem,
        supporting_model_id=None,
    )


def evaluate_single_model(
    source_path: Path,
    model_path: Path,
    use_llm: bool = True,
    llm_model_id: str = "anthropic.claude-3-sonnet-20240229-v1:0",
) -> EvaluationResult:
    """
    Evaluate a single model output against source of truth.
    
    Args:
        source_path: Path to source of truth JSON
        model_path: Path to model output JSON
        use_llm: Whether to use LLM for semantic evaluation
        llm_model_id: Bedrock model ID for LLM evaluation
        
    Returns:
        EvaluationResult with all scores
    """
    start_time = time.time()
    
    log(f"Evaluating: {model_path.name}")
    log("=" * 60)
    
    # Load files
    source_json = load_json_file(source_path)
    model_json = load_json_file(model_path)
    
    # Extract metadata
    metadata = extract_metadata(model_json, model_path)
    log(f"Provider: {metadata.provider}, Model: {metadata.model_id}")
    
    # Level 1: Schema validation
    log("Level 1: Schema Validation...")
    schema_result = validate_schema(model_json)
    log(f"  Schema valid: {schema_result.is_valid}, Errors: {schema_result.error_count}")
    
    # Level 2: Deterministic comparison
    log("Level 2: Deterministic Comparison...")
    section_evaluations = compare_templates(source_json, model_json)
    log(f"  Sections compared: {len(section_evaluations)}")
    
    # Level 3: LLM semantic evaluation (optional)
    if use_llm:
        log("Level 3: LLM Semantic Evaluation...")
        try:
            llm_evaluator = LLMEvaluator(model_id=llm_model_id)
            llm_response = llm_evaluator.evaluate(
                source_json=source_json,
                model_json=model_json,
                schema_errors=schema_result.errors if not schema_result.is_valid else None,
                section_evaluations=section_evaluations,
            )
            section_evaluations = update_evaluations_with_llm_scores(
                section_evaluations, llm_response
            )
            log("  LLM evaluation completed")
        except Exception as e:
            log(f"  LLM evaluation failed: {e}")
            log("  Using deterministic scores only")
    else:
        log("Level 3: Skipped (--no-llm flag)")
    
    # Score all fields
    log("Calculating scores...")
    section_evaluations = score_all_fields(section_evaluations)
    
    # Calculate aggregate scores
    aggregate_scores = calculate_aggregate_scores(schema_result, section_evaluations)
    log(f"  Overall score: {aggregate_scores.overall_score*100:.1f}%")
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Count source sections
    source_sections = extract_sections(source_json)
    model_sections = extract_sections(model_json)
    
    return EvaluationResult(
        source_file=str(source_path),
        model_file=str(model_path),
        metadata=metadata,
        schema_validation=schema_result,
        total_source_sections=len(source_sections),
        total_model_sections=len(model_sections),
        sections=section_evaluations,
        scores=aggregate_scores,
        evaluation_duration_ms=duration_ms,
    )


def create_comparison_report(
    source_path: Path,
    evaluations: list[EvaluationResult],
) -> ComparisonReport:
    """Create a comparison report from multiple evaluations."""
    # Sort by overall score
    sorted_evals = sorted(evaluations, key=lambda e: e.scores.overall_score, reverse=True)
    
    ranked_models = [e.metadata.model_id for e in sorted_evals]
    
    best_model = ranked_models[0] if ranked_models else None
    best_score = sorted_evals[0].scores.overall_score if sorted_evals else None
    
    scores = [e.scores.overall_score for e in evaluations]
    average_score = sum(scores) / len(scores) if scores else None
    
    return ComparisonReport(
        source_file=str(source_path),
        evaluations=evaluations,
        ranked_models=ranked_models,
        best_model=best_model,
        best_score=best_score,
        average_score=average_score,
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate model outputs against source of truth",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Evaluate single model
  python -m evaluation.main --model output/bedrock/model.json --source output/source_of_truth/form.json
  
  # Compare all models
  python -m evaluation.main --source output/source_of_truth/form.json --compare-all
  
  # With visualization
  python -m evaluation.main --source output/source_of_truth/form.json --compare-all --visualize
        """
    )
    
    parser.add_argument(
        "--source", "-s",
        required=True,
        type=Path,
        help="Path to source of truth JSON file"
    )
    
    parser.add_argument(
        "--model", "-m",
        type=Path,
        help="Path to single model output JSON file"
    )
    
    parser.add_argument(
        "--compare-all",
        action="store_true",
        help="Find and compare all model outputs for this source"
    )
    
    parser.add_argument(
        "--output-dir", "-o",
        type=Path,
        default=Path("evaluation_results"),
        help="Directory to save evaluation results (default: evaluation_results)"
    )
    
    parser.add_argument(
        "--visualize",
        action="store_true",
        help="Generate visualization charts"
    )
    
    parser.add_argument(
        "--html",
        action="store_true",
        help="Generate HTML report"
    )
    
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Skip LLM semantic evaluation (faster, less accurate)"
    )
    
    parser.add_argument(
        "--llm-model",
        type=str,
        default="anthropic.claude-3-sonnet-20240229-v1:0",
        help="Bedrock model ID for LLM evaluation"
    )
    
    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="Suppress detailed output"
    )
    
    parser.add_argument(
        "--show-cache",
        action="store_true",
        help="Show cached results summary and exit"
    )
    
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear cache for this source file before running"
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.source.exists():
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)
    
    if args.model and not args.model.exists():
        print(f"Error: Model file not found: {args.model}")
        sys.exit(1)
    
    # Handle show-cache flag
    if args.show_cache:
        cache = load_cache(args.source, args.output_dir)
        print(cache.print_summary())
        sys.exit(0)
    
    # Handle clear-cache flag
    if args.clear_cache:
        cache_path = args.output_dir / f"cache_{args.source.stem}.json"
        if cache_path.exists():
            cache_path.unlink()
            print(f"Cache cleared: {cache_path}")
    
    if not args.model and not args.compare_all:
        print("Error: Specify either --model or --compare-all")
        sys.exit(1)
    
    # Collect model files
    model_files = []
    
    if args.model:
        model_files.append(args.model)
    
    if args.compare_all:
        output_dir = args.source.parent.parent  # Go up from source_of_truth
        found_files = find_model_outputs(output_dir, args.source.name)
        model_files.extend(found_files)
        
        if not model_files:
            print(f"No model output files found for: {args.source.name}")
            sys.exit(1)
        
        print(f"Found {len(model_files)} model output(s) to evaluate")
    
    # Run evaluations
    evaluations = []
    
    for model_path in model_files:
        try:
            result = evaluate_single_model(
                source_path=args.source,
                model_path=model_path,
                use_llm=not args.no_llm,
                llm_model_id=args.llm_model,
            )
            evaluations.append(result)
        except Exception as e:
            print(f"Error evaluating {model_path}: {e}")
            if not args.quiet:
                import traceback
                traceback.print_exc()
    
    if not evaluations:
        print("No successful evaluations")
        sys.exit(1)
    
    # Create comparison report
    report = create_comparison_report(args.source, evaluations)
    
    # Print console report
    console_output = generate_console_report(report)
    print(console_output)
    
    # Save outputs
    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # JSON report
    json_path = args.output_dir / f"evaluation_{timestamp}.json"
    generate_json_report(report, json_path)
    print(f"\nJSON report saved: {json_path}")
    
    # Charts
    chart_paths = {}
    if args.visualize:
        charts_dir = args.output_dir / f"charts_{timestamp}"
        chart_paths = generate_all_charts(report, charts_dir)
        print(f"Charts saved: {charts_dir}")
    
    # HTML report
    if args.html:
        html_path = args.output_dir / f"report_{timestamp}.html"
        generate_html_report(report, html_path, chart_paths)
        print(f"HTML report saved: {html_path}")
    
    # Update cache with new results
    cache = update_cache_with_results(evaluations, args.source, args.output_dir)
    cache_path = args.output_dir / f"cache_{args.source.stem}.json"
    print(f"\nCache updated: {cache_path}")
    print(cache.print_summary())


if __name__ == "__main__":
    main()

