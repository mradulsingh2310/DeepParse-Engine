"""
Evaluation Runner

Provides a simple interface to run evaluation after PDF extraction.
Called automatically from main.py after generating outputs.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import TypedDict

from evaluation.models import (
    EvaluationResult,
    ModelMetadata,
)
from evaluation.schema_validator import validate_schema
from evaluation.field_comparator import (
    load_json_file,
    compare_templates,
    extract_sections,
)
from evaluation.scorer import (
    score_all_fields,
    calculate_aggregate_scores,
)
from evaluation.cache import (
    load_cache,
    save_cache,
    EvaluationCache,
)

from src.utils.logger import log


class UsageData(TypedDict):
    """Usage data for a single model run."""
    cost: float
    input_tokens: int
    output_tokens: int


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


def extract_usage_from_metadata(json_data: dict) -> UsageData:
    """
    Extract usage data (cost, tokens) from JSON _metadata.
    
    Args:
        json_data: The model output JSON containing _metadata
        
    Returns:
        UsageData dict with cost, input_tokens, output_tokens
    """
    metadata = json_data.get("_metadata", {})
    return {
        "cost": metadata.get("cost_usd", 0.0),
        "input_tokens": metadata.get("input_tokens", 0),
        "output_tokens": metadata.get("output_tokens", 0),
    }


def evaluate_model_output(
    source_path: Path,
    model_path: Path,
) -> EvaluationResult:
    """
    Evaluate a single model output against source of truth.
    
    Uses deterministic comparison only (no LLM) for speed during automated runs.
    
    Args:
        source_path: Path to source of truth JSON
        model_path: Path to model output JSON
        
    Returns:
        EvaluationResult with all scores
    """
    start_time = time.time()
    
    # Load files
    source_json = load_json_file(source_path)
    model_json = load_json_file(model_path)
    
    # Extract metadata
    metadata = extract_metadata(model_json, model_path)
    
    # Level 1: Schema validation
    schema_result = validate_schema(model_json)
    
    # Level 2: Deterministic comparison
    section_evaluations = compare_templates(source_json, model_json)
    
    # Score all fields (using deterministic scores only)
    section_evaluations = score_all_fields(section_evaluations)
    
    # Calculate aggregate scores
    aggregate_scores = calculate_aggregate_scores(schema_result, section_evaluations)
    
    duration_ms = int((time.time() - start_time) * 1000)
    
    # Count sections
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


def find_source_of_truth(pdf_stem: str, source_dir: Path) -> Path | None:
    """Find source of truth file for a PDF."""
    # Try exact match first
    exact_path = source_dir / f"{pdf_stem}.json"
    if exact_path.exists():
        return exact_path
    
    # Try finding by pattern
    for path in source_dir.glob("*.json"):
        if pdf_stem.lower() in path.stem.lower():
            return path
    
    return None


def run_evaluation_for_outputs(
    model_output_paths: list[Path],
    source_of_truth_dir: Path,
    cache_dir: Path,
    usage_data: dict[str, UsageData] | None = None,
    quiet: bool = False,
) -> dict[str, EvaluationCache]:
    """
    Run evaluation for multiple model outputs and update caches.

    Args:
        model_output_paths: List of model output JSON files
        source_of_truth_dir: Directory containing source of truth files
        cache_dir: Directory for cache files
        usage_data: Optional dict mapping "{provider}:{model_id}" to UsageData.
                    If not provided, usage will be read from each file's _metadata.
        quiet: If True, suppress detailed output

    Returns:
        Dictionary mapping source files to their updated caches
    """
    usage_data = usage_data or {}

    # Group outputs by their source of truth
    outputs_by_source: dict[str, list[Path]] = {}

    for output_path in model_output_paths:
        # Extract PDF stem from output path
        # Output structure: output/{provider}/{model}/{pdf_stem}.json
        pdf_stem = output_path.stem

        # Find corresponding source of truth
        source_path = find_source_of_truth(pdf_stem, source_of_truth_dir)

        if source_path:
            key = str(source_path)
            if key not in outputs_by_source:
                outputs_by_source[key] = []
            outputs_by_source[key].append(output_path)
        elif not quiet:
            log(f"Warning: No source of truth found for {output_path.name}")

    # Process each source of truth
    caches: dict[str, EvaluationCache] = {}

    for source_path_str, output_paths in outputs_by_source.items():
        source_path = Path(source_path_str)

        if not quiet:
            log(f"\nEvaluating against: {source_path.name}")
            log(f"  Model outputs: {len(output_paths)}")

        # Load existing cache
        cache = load_cache(source_path, cache_dir)

        for output_path in output_paths:
            try:
                result = evaluate_model_output(source_path, output_path)

                # Get usage data for this model - first try passed usage_data,
                # then fall back to reading from the output file's _metadata
                model_key = f"{result.metadata.provider}:{result.metadata.model_id}"
                model_usage = usage_data.get(model_key)

                if not model_usage:
                    # Read usage from the output file's _metadata
                    model_json = load_json_file(output_path)
                    model_usage = extract_usage_from_metadata(model_json)

                # Add evaluation with usage data
                cache.add_evaluation(
                    result,
                    cost=model_usage.get("cost", 0.0),
                    input_tokens=model_usage.get("input_tokens", 0),
                    output_tokens=model_usage.get("output_tokens", 0),
                )

                cost_str = f" (${model_usage.get('cost', 0):.4f})" if model_usage.get("cost", 0) > 0 else ""
                if not quiet:
                    log(f"  [{result.metadata.provider}] {result.metadata.model_id}: "
                        f"{result.scores.overall_score*100:.1f}%{cost_str}")
            except Exception as e:
                if not quiet:
                    log(f"  Error evaluating {output_path.name}: {e}")

        # Save updated cache
        save_cache(cache, cache_dir)
        caches[source_path_str] = cache

        if not quiet:
            log(f"\n  Cache updated: {len(cache.models)} models tracked")

    return caches


def run_post_extraction_evaluation(
    output_dir: Path,
    source_of_truth_dir: Path | None = None,
    cache_dir: Path | None = None,
    usage_data: dict[str, UsageData] | None = None,
    quiet: bool = False,
) -> None:
    """
    Run evaluation automatically after PDF extraction.

    This is the main entry point called from main.py.

    Args:
        output_dir: Directory containing model outputs
        source_of_truth_dir: Directory containing source of truth files
                            (defaults to output/source_of_truth)
        cache_dir: Directory for evaluation cache files
                   (defaults to evaluation_results)
        usage_data: Optional dict mapping "{provider}:{model_id}" to UsageData
                    containing cost and token information
        quiet: If True, suppress output
    """
    if source_of_truth_dir is None:
        source_of_truth_dir = output_dir / "source_of_truth"
    
    if cache_dir is None:
        cache_dir = Path("evaluation_results")
    
    # Check if source of truth directory exists
    if not source_of_truth_dir.exists():
        if not quiet:
            log(f"Source of truth directory not found: {source_of_truth_dir}")
            log("Skipping automatic evaluation.")
        return
    
    # Find all source of truth files
    source_files = list(source_of_truth_dir.glob("*.json"))
    if not source_files:
        if not quiet:
            log("No source of truth files found. Skipping evaluation.")
        return
    
    if not quiet:
        log("")
        log("=" * 70)
        log("AUTOMATIC EVALUATION")
        log("=" * 70)
    
    # Find all model output files (excluding source of truth)
    model_outputs: list[Path] = []
    
    for json_file in output_dir.rglob("*.json"):
        # Skip source of truth files
        if "source_of_truth" in str(json_file):
            continue
        # Skip cache files
        if json_file.name.startswith("cache_"):
            continue
        # Skip evaluation reports
        if "evaluation" in json_file.name:
            continue
        
        model_outputs.append(json_file)
    
    if not model_outputs:
        if not quiet:
            log("No model outputs found to evaluate.")
        return
    
    if not quiet:
        log(f"Found {len(model_outputs)} model output(s) to evaluate")
        log(f"Source of truth files: {len(source_files)}")
    
    # Run evaluation
    caches = run_evaluation_for_outputs(
        model_output_paths=model_outputs,
        source_of_truth_dir=source_of_truth_dir,
        cache_dir=cache_dir,
        usage_data=usage_data,
        quiet=quiet,
    )
    
    # Print summary for each cache
    if not quiet and caches:
        for source_path, cache in caches.items():
            print(cache.print_summary())

