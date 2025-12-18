"""
Evaluation Results Cache

Stores and retrieves evaluation results from a JSON cache file.
Supports averaging results across multiple runs.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from evaluation.models import EvaluationResult, AggregateScores


class CachedModelResult(BaseModel):
    """Cached evaluation result for a single model across multiple runs."""
    model_id: str
    provider: str
    run_count: int = 0

    # Cumulative scores (sum across runs, divide by run_count for average)
    total_schema_compliance: float = 0.0
    total_structural_accuracy: float = 0.0
    total_semantic_accuracy: float = 0.0
    total_config_accuracy: float = 0.0
    total_overall_score: float = 0.0

    # Cumulative cost/token tracking
    total_cost: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0

    # Best run
    best_score: float = 0.0
    best_run_timestamp: str | None = None

    # Latest run
    latest_score: float = 0.0
    latest_run_timestamp: str | None = None

    # Individual run scores (for detailed history)
    run_history: list[dict[str, Any]] = Field(default_factory=list)
    
    def add_run(
        self,
        result: EvaluationResult,
        cost: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """
        Add a new evaluation run to the cache.

        Args:
            result: The evaluation result
            cost: Cost in USD for this run
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
        """
        self.run_count += 1

        scores = result.scores
        self.total_schema_compliance += scores.schema_compliance
        self.total_structural_accuracy += scores.structural_accuracy
        self.total_semantic_accuracy += scores.semantic_accuracy
        self.total_config_accuracy += scores.config_accuracy
        self.total_overall_score += scores.overall_score

        # Update cost/token totals
        self.total_cost += cost
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens

        # Update best
        if scores.overall_score > self.best_score:
            self.best_score = scores.overall_score
            self.best_run_timestamp = result.timestamp

        # Update latest
        self.latest_score = scores.overall_score
        self.latest_run_timestamp = result.timestamp

        # Add to history (keep last 10 runs)
        self.run_history.append({
            "timestamp": result.timestamp,
            "overall_score": scores.overall_score,
            "schema_compliance": scores.schema_compliance,
            "structural_accuracy": scores.structural_accuracy,
            "semantic_accuracy": scores.semantic_accuracy,
            "config_accuracy": scores.config_accuracy,
            "cost": cost,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        })
        if len(self.run_history) > 10:
            self.run_history = self.run_history[-10:]
    
    @property
    def avg_schema_compliance(self) -> float:
        return self.total_schema_compliance / self.run_count if self.run_count > 0 else 0.0
    
    @property
    def avg_structural_accuracy(self) -> float:
        return self.total_structural_accuracy / self.run_count if self.run_count > 0 else 0.0
    
    @property
    def avg_semantic_accuracy(self) -> float:
        return self.total_semantic_accuracy / self.run_count if self.run_count > 0 else 0.0
    
    @property
    def avg_config_accuracy(self) -> float:
        return self.total_config_accuracy / self.run_count if self.run_count > 0 else 0.0
    
    @property
    def avg_overall_score(self) -> float:
        return self.total_overall_score / self.run_count if self.run_count > 0 else 0.0

    @property
    def avg_cost(self) -> float:
        return self.total_cost / self.run_count if self.run_count > 0 else 0.0

    def get_average_scores(self) -> AggregateScores:
        """Get average scores across all runs."""
        return AggregateScores(
            schema_compliance=round(self.avg_schema_compliance, 4),
            structural_accuracy=round(self.avg_structural_accuracy, 4),
            semantic_accuracy=round(self.avg_semantic_accuracy, 4),
            config_accuracy=round(self.avg_config_accuracy, 4),
            overall_score=round(self.avg_overall_score, 4),
        )


class EvaluationCache(BaseModel):
    """Cache for all evaluation results."""
    source_file: str
    last_updated: str = Field(default_factory=lambda: datetime.now().isoformat())
    models: dict[str, CachedModelResult] = Field(default_factory=dict)
    
    def get_or_create_model(self, model_id: str, provider: str) -> CachedModelResult:
        """Get existing model cache or create new one."""
        key = f"{provider}:{model_id}"
        if key not in self.models:
            self.models[key] = CachedModelResult(model_id=model_id, provider=provider)
        return self.models[key]
    
    def add_evaluation(
        self,
        result: EvaluationResult,
        cost: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
    ) -> None:
        """
        Add an evaluation result to the cache.

        Args:
            result: The evaluation result
            cost: Cost in USD for this run
            input_tokens: Number of input tokens used
            output_tokens: Number of output tokens used
        """
        model_cache = self.get_or_create_model(
            result.metadata.model_id,
            result.metadata.provider
        )
        model_cache.add_run(result, cost, input_tokens, output_tokens)
        self.last_updated = datetime.now().isoformat()
    
    def get_rankings(self) -> list[tuple[str, float, int]]:
        """
        Get model rankings by average overall score.
        
        Returns list of (model_key, avg_score, run_count) sorted by score desc.
        """
        rankings = []
        for key, model in self.models.items():
            rankings.append((key, model.avg_overall_score, model.run_count))
        return sorted(rankings, key=lambda x: x[1], reverse=True)
    
    def print_summary(self) -> str:
        """Generate a summary of cached results."""
        lines = []
        lines.append("=" * 80)
        lines.append("EVALUATION CACHE SUMMARY")
        lines.append("=" * 80)
        lines.append(f"Source: {self.source_file}")
        lines.append(f"Last Updated: {self.last_updated}")
        lines.append(f"Models Tracked: {len(self.models)}")

        # Calculate total cost
        total_cost = sum(m.total_cost for m in self.models.values())
        if total_cost > 0:
            lines.append(f"Total Cost: ${total_cost:.4f}")
        lines.append("")

        rankings = self.get_rankings()
        if rankings:
            lines.append("Model Rankings (by average overall score):")
            lines.append("-" * 80)
            lines.append(f"{'Rank':<5} {'Model':<35} {'Avg Score':<12} {'Runs':<6} {'Cost':<10}")
            lines.append("-" * 80)

            for i, (key, avg_score, run_count) in enumerate(rankings, 1):
                model = self.models[key]
                cost_str = f"${model.total_cost:.4f}" if model.total_cost > 0 else "-"
                lines.append(f"{i:<5} {key:<35} {avg_score*100:>6.1f}%      {run_count:<6} {cost_str:<10}")

            lines.append("-" * 80)

            # Best model
            best = rankings[0]
            lines.append(f"\nBest Model: {best[0]}")
            lines.append(f"Average Score: {best[1]*100:.1f}% (over {best[2]} runs)")

        lines.append("=" * 80)
        return "\n".join(lines)


def get_cache_path(source_file: str | Path, cache_dir: str | Path = "evaluation_results") -> Path:
    """Get the cache file path for a source file."""
    cache_dir = Path(cache_dir)
    source_stem = Path(source_file).stem
    return cache_dir / f"cache_{source_stem}.json"


def load_cache(source_file: str | Path, cache_dir: str | Path = "evaluation_results") -> EvaluationCache:
    """Load cache from file or create new one."""
    cache_path = get_cache_path(source_file, cache_dir)
    
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return EvaluationCache.model_validate(data)
        except Exception as e:
            print(f"Warning: Failed to load cache from {cache_path}: {e}")
    
    return EvaluationCache(source_file=str(source_file))


def save_cache(cache: EvaluationCache, cache_dir: str | Path = "evaluation_results") -> Path:
    """Save cache to file."""
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    cache_path = get_cache_path(cache.source_file, cache_dir)
    
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(cache.model_dump(mode="json"), f, indent=2)
    
    return cache_path


def update_cache_with_results(
    evaluations: list[EvaluationResult],
    source_file: str | Path,
    cache_dir: str | Path = "evaluation_results",
) -> EvaluationCache:
    """
    Update cache with new evaluation results.
    
    Args:
        evaluations: List of new evaluation results
        source_file: Path to source of truth file
        cache_dir: Directory for cache files
        
    Returns:
        Updated cache
    """
    cache = load_cache(source_file, cache_dir)
    
    for result in evaluations:
        cache.add_evaluation(result)
    
    save_cache(cache, cache_dir)
    return cache

