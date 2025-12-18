"""
Visualization Module

Generates charts and graphs for evaluation results using matplotlib and plotly.
"""

from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt  # type: ignore[import-untyped]
import numpy as np

from evaluation.models import (
    EvaluationResult,
    ComparisonReport,
)


# Color palette for charts
COLORS = {
    "primary": "#2563eb",      # Blue
    "secondary": "#7c3aed",    # Purple  
    "success": "#059669",      # Green
    "warning": "#d97706",      # Orange
    "danger": "#dc2626",       # Red
    "neutral": "#6b7280",      # Gray
}

SCORE_COLORS = [
    "#dc2626",  # 0-20% Red
    "#ea580c",  # 20-40% Orange
    "#d97706",  # 40-60% Amber
    "#65a30d",  # 60-80% Lime
    "#059669",  # 80-100% Green
]


def get_score_color(score: float) -> str:
    """Get color based on score value (0.0-1.0)."""
    idx = min(int(score * 5), 4)
    return SCORE_COLORS[idx]


def create_bar_chart(
    results: list[EvaluationResult],
    output_path: str | Path,
    title: str = "Model Performance Comparison",
) -> Path:
    """
    Create a horizontal bar chart comparing overall scores across models.
    
    Args:
        results: List of evaluation results
        output_path: Path to save the chart
        title: Chart title
        
    Returns:
        Path to saved chart
    """
    output_path = Path(output_path)
    
    # Extract data
    model_names = [r.metadata.model_id for r in results]
    scores = [r.scores.overall_score * 100 for r in results]
    colors = [get_score_color(r.scores.overall_score) for r in results]
    
    # Sort by score descending
    sorted_data = sorted(zip(model_names, scores, colors), key=lambda x: x[1], reverse=True)
    if sorted_data:
        model_names_sorted, scores_sorted, colors_sorted = zip(*sorted_data)
        model_names = list(model_names_sorted)
        scores = list(scores_sorted)
        colors = list(colors_sorted)
    else:
        model_names, scores, colors = [], [], []
    
    # Create figure
    _, ax = plt.subplots(figsize=(10, max(4, len(model_names) * 0.8)))
    
    # Create horizontal bars
    y_pos = np.arange(len(model_names))
    bars = ax.barh(y_pos, scores, color=colors, edgecolor="white", linewidth=0.5)
    
    # Add score labels
    for bar, score in zip(bars, scores):
        width = bar.get_width()
        ax.text(width + 1, bar.get_y() + bar.get_height()/2,
                f"{score:.1f}%", va="center", ha="left", fontsize=10, fontweight="bold")
    
    # Customize
    ax.set_yticks(y_pos)
    ax.set_yticklabels(model_names, fontsize=10)
    ax.set_xlabel("Overall Score (%)", fontsize=12)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    ax.set_xlim(0, 110)
    ax.invert_yaxis()
    
    # Add grid
    ax.xaxis.grid(True, linestyle="--", alpha=0.3)
    ax.set_axisbelow(True)
    
    # Style
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    
    return output_path


def create_radar_chart(
    results: list[EvaluationResult],
    output_path: str | Path,
    title: str = "Multi-dimensional Comparison",
) -> Path:
    """
    Create a radar chart comparing multiple dimensions across models.
    
    Args:
        results: List of evaluation results
        output_path: Path to save the chart
        title: Chart title
        
    Returns:
        Path to saved chart
    """
    output_path = Path(output_path)
    
    # Dimensions to compare
    dimensions = ["Schema", "Structure", "Semantic", "Config"]
    num_dims = len(dimensions)
    
    # Calculate angles for radar
    angles = [n / float(num_dims) * 2 * math.pi for n in range(num_dims)]
    angles += angles[:1]  # Complete the loop
    
    # Create figure
    _, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    
    # Colors for each model
    model_colors = plt.cm.Set2(np.linspace(0, 1, len(results)))
    
    for i, result in enumerate(results):
        # Extract scores
        scores = [
            result.scores.schema_compliance,
            result.scores.structural_accuracy,
            result.scores.semantic_accuracy,
            result.scores.config_accuracy,
        ]
        scores += scores[:1]  # Complete the loop
        
        # Plot
        ax.plot(angles, scores, "o-", linewidth=2, 
                label=result.metadata.model_id, color=model_colors[i])
        ax.fill(angles, scores, alpha=0.15, color=model_colors[i])
    
    # Customize
    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(dimensions, fontsize=11)
    ax.set_ylim(0, 1)
    ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
    ax.set_yticklabels(["20%", "40%", "60%", "80%", "100%"], fontsize=9)
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    
    # Legend
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.0), fontsize=9)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    
    return output_path


def create_heatmap(
    result: EvaluationResult,
    output_path: str | Path,
    title: str | None = None,
) -> Path:
    """
    Create a heatmap showing section-wise accuracy for a single model.
    
    Args:
        result: Single evaluation result
        output_path: Path to save the chart
        title: Chart title (defaults to model name)
        
    Returns:
        Path to saved chart
    """
    output_path = Path(output_path)
    
    if title is None:
        title = f"Section Accuracy: {result.metadata.model_id}"
    
    sections = result.sections
    if not sections:
        # Create empty chart
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No sections to display", ha="center", va="center")
        plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close()
        return output_path
    
    # Prepare data
    section_names = [s.source_section_name[:20] for s in sections]
    metrics = ["Name Match", "Field Count", "Avg Field Score", "Section Score"]
    
    # Build data matrix
    data_list: list[list[float]] = []
    for section in sections:
        field_scores = [f.overall_score for f in section.fields]
        avg_score = float(np.mean(field_scores)) if field_scores else 0.0
        row = [
            section.section_name_similarity,
            1.0 if section.field_count_match else 0.0,
            avg_score,
            section.section_score,
        ]
        data_list.append(row)
    
    data = np.array(data_list)
    
    # Create figure
    _, ax = plt.subplots(figsize=(10, max(4, len(sections) * 0.5)))
    
    # Create heatmap
    im = ax.imshow(data, cmap="RdYlGn", aspect="auto", vmin=0, vmax=1)
    
    # Set ticks
    ax.set_xticks(np.arange(len(metrics)))
    ax.set_yticks(np.arange(len(section_names)))
    ax.set_xticklabels(metrics, fontsize=10)
    ax.set_yticklabels(section_names, fontsize=9)
    
    # Rotate x labels
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right", rotation_mode="anchor")
    
    # Add text annotations
    for i in range(len(section_names)):
        for j in range(len(metrics)):
            value = float(data[i][j])
            text_color = "white" if value < 0.5 else "black"
            ax.text(j, i, f"{value:.2f}", ha="center", va="center",
                   color=text_color, fontsize=9)
    
    # Title and colorbar
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    cbar = ax.figure.colorbar(im, ax=ax, shrink=0.8)
    cbar.ax.set_ylabel("Score", rotation=-90, va="bottom", fontsize=10)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    
    return output_path


def create_summary_table_image(
    results: list[EvaluationResult],
    output_path: str | Path,
    title: str = "Evaluation Summary",
) -> Path:
    """
    Create a table image showing summary scores.
    
    Args:
        results: List of evaluation results
        output_path: Path to save the image
        title: Table title
        
    Returns:
        Path to saved image
    """
    output_path = Path(output_path)
    
    # Prepare data
    columns = ["Model", "Schema", "Structure", "Semantic", "Config", "Overall"]
    rows = []
    
    for result in sorted(results, key=lambda r: r.scores.overall_score, reverse=True):
        rows.append([
            result.metadata.model_id[:30],
            f"{result.scores.schema_compliance*100:.1f}%",
            f"{result.scores.structural_accuracy*100:.1f}%",
            f"{result.scores.semantic_accuracy*100:.1f}%",
            f"{result.scores.config_accuracy*100:.1f}%",
            f"{result.scores.overall_score*100:.1f}%",
        ])
    
    # Create figure
    _, ax = plt.subplots(figsize=(12, max(3, len(rows) * 0.5 + 1)))
    ax.axis("off")
    
    # Create table
    table = ax.table(
        cellText=rows,
        colLabels=columns,
        loc="center",
        cellLoc="center",
    )
    
    # Style table
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.5)
    
    # Header styling
    for j, _ in enumerate(columns):
        cell = table[(0, j)]
        cell.set_facecolor(COLORS["primary"])
        cell.set_text_props(color="white", fontweight="bold")
    
    # Color code overall score cells
    for i, result in enumerate(sorted(results, key=lambda r: r.scores.overall_score, reverse=True)):
        cell = table[(i + 1, 5)]
        cell.set_facecolor(get_score_color(result.scores.overall_score))
        cell.set_text_props(color="white", fontweight="bold")
    
    ax.set_title(title, fontsize=14, fontweight="bold", pad=20)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close()
    
    return output_path


def generate_all_charts(
    report: ComparisonReport,
    output_dir: str | Path,
) -> dict[str, Path]:
    """
    Generate all visualization charts for a comparison report.
    
    Args:
        report: ComparisonReport with evaluation results
        output_dir: Directory to save charts
        
    Returns:
        Dictionary mapping chart names to file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    charts: dict[str, Path] = {}
    
    if not report.evaluations:
        return charts
    
    # Bar chart
    charts["bar_chart"] = create_bar_chart(
        report.evaluations,
        output_dir / "bar_chart.png",
    )
    
    # Radar chart
    charts["radar_chart"] = create_radar_chart(
        report.evaluations,
        output_dir / "radar_chart.png",
    )
    
    # Summary table
    charts["summary_table"] = create_summary_table_image(
        report.evaluations,
        output_dir / "summary_table.png",
    )
    
    # Heatmaps for each model
    for result in report.evaluations:
        model_name = result.metadata.model_id.replace("/", "_").replace(":", "_")
        chart_path = create_heatmap(
            result,
            output_dir / f"heatmap_{model_name}.png",
        )
        charts[f"heatmap_{model_name}"] = chart_path
    
    return charts

