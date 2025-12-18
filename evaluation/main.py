"""
Evaluation CLI Entry Point

Automatically discovers all model outputs and compares them against source of truth.
Generates visualizations, HTML reports, and uses LLM for semantic evaluation.
"""

from __future__ import annotations

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
from evaluation.cache import update_cache_with_results

from src.config.loader import load_config
from src.utils.logger import log


# Constants
LLM_MODEL_ID = "moonshot.kimi-k2-thinking"
OUTPUT_DIR = Path("output")
SOURCE_OF_TRUTH_DIR = Path("source_of_truth")
RESULTS_DIR = Path("evaluation_results")


def find_source_of_truth_files(source_dir: Path) -> list[Path]:
    """Find all source of truth JSON files."""
    if not source_dir.exists():
        return []
    return list(source_dir.glob("*.json"))


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
    elif "google" in filename:
        provider = "google"
    elif "anthropic" in filename:
        provider = "anthropic"
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
) -> EvaluationResult:
    """
    Evaluate a single model output against source of truth.
    
    Args:
        source_path: Path to source of truth JSON
        model_path: Path to model output JSON
        
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
    
    # Level 3: LLM semantic evaluation
    log(f"Level 3: LLM Semantic Evaluation (using {LLM_MODEL_ID})...")
    try:
        llm_evaluator = LLMEvaluator(model_id=LLM_MODEL_ID)
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


def run_evaluation_for_source(
    source_path: Path,
) -> ComparisonReport | None:
    """
    Run evaluation for a single source of truth file.
    
    Returns ComparisonReport or None if no model outputs found.
    """
    log(f"\n{'='*80}")
    log(f"Source: {source_path.name}")
    log(f"{'='*80}")
    
    # Find model outputs for this source
    model_files = find_model_outputs(OUTPUT_DIR, source_path.name)
    
    if not model_files:
        log(f"No model outputs found for: {source_path.name}")
        return None
    
    log(f"Found {len(model_files)} model output(s)")
    for f in model_files:
        log(f"  - {f.relative_to(OUTPUT_DIR)}")
    
    # Run evaluations
    evaluations = []
    
    for model_path in model_files:
        try:
            result = evaluate_single_model(
                source_path=source_path,
                model_path=model_path,
            )
            evaluations.append(result)
        except Exception as e:
            log(f"Error evaluating {model_path}: {e}")
            import traceback
            traceback.print_exc()
    
    if not evaluations:
        log("No successful evaluations")
        return None
    
    # Create comparison report
    report = create_comparison_report(source_path, evaluations)
    
    # Print console report
    console_output = generate_console_report(report)
    print(console_output)
    
    # Save outputs
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    source_stem = source_path.stem
    
    # JSON report
    json_path = RESULTS_DIR / f"evaluation_{source_stem}_{timestamp}.json"
    generate_json_report(report, json_path)
    log(f"JSON report saved: {json_path}")
    
    # Charts
    charts_dir = RESULTS_DIR / f"charts_{source_stem}_{timestamp}"
    chart_paths = generate_all_charts(report, charts_dir)
    log(f"Charts saved: {charts_dir}")
    
    # HTML report
    html_path = RESULTS_DIR / f"report_{source_stem}_{timestamp}.html"
    generate_html_report(report, html_path, chart_paths)
    log(f"HTML report saved: {html_path}")
    
    # Update cache
    update_cache_with_results(evaluations, source_path, RESULTS_DIR)
    cache_path = RESULTS_DIR / f"cache_{source_stem}.json"
    log(f"Cache updated: {cache_path}")
    
    return report


def main():
    """Main entry point."""
    # Load config to display provider info
    config = load_config()
    
    log("=" * 80)
    log("OCR-AI Evaluation Pipeline")
    log("=" * 80)
    log(f"Output directory: {OUTPUT_DIR}")
    log(f"Results directory: {RESULTS_DIR}")
    log(f"LLM model: {LLM_MODEL_ID}")
    
    # Show configured providers
    log("\nConfigured Providers:")
    if config.providers.bedrock.models:
        log(f"  Bedrock: {len(config.providers.bedrock.models)} model(s)")
    if config.providers.deepseek.models:
        log(f"  Deepseek: {len(config.providers.deepseek.models)} model(s)")
    if config.providers.google.models:
        log(f"  Google: {len(config.providers.google.models)} model(s)")
    if config.providers.anthropic.models:
        log(f"  Anthropic: {len(config.providers.anthropic.models)} model(s)")
    
    # Auto-discover source of truth files
    source_files = find_source_of_truth_files(SOURCE_OF_TRUTH_DIR)
    
    if not source_files:
        print(f"Error: No source of truth files found in: {SOURCE_OF_TRUTH_DIR}")
        print("Please add JSON files to source_of_truth/ directory")
        sys.exit(1)
    
    log(f"\nSource of truth files: {len(source_files)}")
    for f in source_files:
        log(f"  - {f.name}")
    
    # Run evaluations for each source
    all_reports = []
    
    for source_path in source_files:
        report = run_evaluation_for_source(source_path)
        if report:
            all_reports.append(report)
    
    # Summary
    log("\n" + "=" * 80)
    log("EVALUATION SUMMARY")
    log("=" * 80)
    
    if not all_reports:
        log("No evaluations completed successfully")
        sys.exit(1)
    
    for report in all_reports:
        source_name = Path(report.source_file).name
        log(f"\n{source_name}:")
        log(f"  Models evaluated: {len(report.evaluations)}")
        log(f"  Best model: {report.best_model}")
        log(f"  Best score: {report.best_score*100:.1f}%" if report.best_score else "  Best score: N/A")
        log(f"  Average score: {report.average_score*100:.1f}%" if report.average_score else "  Average score: N/A")
    
    log("\nEvaluation complete!")


if __name__ == "__main__":
    main()
