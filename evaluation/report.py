"""
Report Generator

Generates evaluation reports in JSON, HTML, and console formats.
"""

from __future__ import annotations

import json
from pathlib import Path

from tabulate import tabulate  # type: ignore[import-untyped]

from evaluation.models import ComparisonReport


def generate_json_report(
    report: ComparisonReport,
    output_path: str | Path,
    indent: int = 2,
) -> Path:
    """
    Generate a JSON report file.
    
    Args:
        report: ComparisonReport to serialize
        output_path: Path to save the report
        indent: JSON indentation level
        
    Returns:
        Path to saved report
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Serialize using Pydantic
    report_dict = report.model_dump(mode="json")
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report_dict, f, indent=indent, ensure_ascii=False)
    
    return output_path


def generate_console_report(report: ComparisonReport) -> str:
    """
    Generate a console-friendly text report.
    
    Args:
        report: ComparisonReport to format
        
    Returns:
        Formatted string report
    """
    lines = []
    lines.append("=" * 80)
    lines.append("INSPECTION TEMPLATE EVALUATION REPORT")
    lines.append("=" * 80)
    lines.append(f"Source: {report.source_file}")
    lines.append(f"Generated: {report.timestamp}")
    lines.append("")
    
    if not report.evaluations:
        lines.append("No evaluations found.")
        return "\n".join(lines)
    
    # Summary table
    lines.append("-" * 80)
    lines.append("SUMMARY")
    lines.append("-" * 80)
    
    table_data = []
    for result in sorted(report.evaluations, key=lambda r: r.scores.overall_score, reverse=True):
        table_data.append([
            result.metadata.model_id[:40],
            f"{result.scores.schema_compliance*100:.1f}%",
            f"{result.scores.structural_accuracy*100:.1f}%",
            f"{result.scores.semantic_accuracy*100:.1f}%",
            f"{result.scores.config_accuracy*100:.1f}%",
            f"{result.scores.overall_score*100:.1f}%",
        ])
    
    headers = ["Model", "Schema", "Structure", "Semantic", "Config", "Overall"]
    lines.append(tabulate(table_data, headers=headers, tablefmt="grid"))
    lines.append("")
    
    # Best model
    if report.best_model and report.best_score is not None and report.average_score is not None:
        lines.append(f"Best Model: {report.best_model}")
        lines.append(f"Best Score: {report.best_score*100:.1f}%")
        lines.append(f"Average Score: {report.average_score*100:.1f}%")
    lines.append("")
    
    # Detailed results for each model
    for result in report.evaluations:
        lines.append("-" * 80)
        lines.append(f"MODEL: {result.metadata.model_id}")
        lines.append(f"Provider: {result.metadata.provider}")
        lines.append("-" * 80)
        
        # Schema validation
        if result.schema_validation.is_valid:
            lines.append("Schema Validation: PASSED")
        else:
            lines.append(f"Schema Validation: FAILED ({result.schema_validation.error_count} errors)")
            for error in result.schema_validation.errors[:5]:
                lines.append(f"  - {error.path}: {error.message}")
            if result.schema_validation.error_count > 5:
                lines.append(f"  ... and {result.schema_validation.error_count - 5} more errors")
        lines.append("")
        
        # Section summary
        lines.append("Sections:")
        section_data = []
        for section in result.sections:
            section_data.append([
                section.source_section_name[:25],
                section.model_section_name[:25] if section.model_section_name else "MISSING",
                f"{section.section_name_similarity*100:.0f}%",
                f"{section.matched_fields}/{section.source_field_count}",
                f"{section.section_score*100:.0f}%",
            ])
        
        section_headers = ["Source Section", "Model Section", "Name Match", "Fields", "Score"]
        lines.append(tabulate(section_data, headers=section_headers, tablefmt="simple"))
        lines.append("")
    
    lines.append("=" * 80)
    lines.append("END OF REPORT")
    lines.append("=" * 80)
    
    return "\n".join(lines)


def generate_html_report(
    report: ComparisonReport,
    output_path: str | Path,
    chart_paths: dict[str, Path] | None = None,
) -> Path:
    """
    Generate an HTML report with embedded charts.
    
    Args:
        report: ComparisonReport to format
        output_path: Path to save the HTML report
        chart_paths: Optional dictionary of chart names to paths
        
    Returns:
        Path to saved report
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build HTML
    html_parts = [
        "<!DOCTYPE html>",
        "<html lang='en'>",
        "<head>",
        "  <meta charset='UTF-8'>",
        "  <meta name='viewport' content='width=device-width, initial-scale=1.0'>",
        "  <title>Inspection Template Evaluation Report</title>",
        "  <style>",
        _get_css_styles(),
        "  </style>",
        "</head>",
        "<body>",
        "  <div class='container'>",
    ]
    
    # Header
    html_parts.append(f"""
    <header>
      <h1>Inspection Template Evaluation Report</h1>
      <p class='subtitle'>Generated: {report.timestamp}</p>
      <p class='source'>Source: <code>{report.source_file}</code></p>
    </header>
    """)
    
    if not report.evaluations:
        html_parts.append("<p class='warning'>No evaluations found.</p>")
    else:
        # Summary section
        html_parts.append(_generate_summary_html(report))
        
        # Charts section
        if chart_paths:
            html_parts.append(_generate_charts_html(chart_paths, output_path.parent))
        
        # Detailed results
        html_parts.append(_generate_details_html(report))
    
    html_parts.extend([
        "  </div>",
        "</body>",
        "</html>",
    ])
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
    
    return output_path


def _get_css_styles() -> str:
    """Return CSS styles for HTML report."""
    return """
    :root {
      --primary: #2563eb;
      --success: #059669;
      --warning: #d97706;
      --danger: #dc2626;
      --bg: #f8fafc;
      --card-bg: #ffffff;
      --text: #1e293b;
      --text-muted: #64748b;
      --border: #e2e8f0;
    }
    
    * { box-sizing: border-box; margin: 0; padding: 0; }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background: var(--bg);
      color: var(--text);
      line-height: 1.6;
    }
    
    .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
    
    header {
      text-align: center;
      margin-bottom: 2rem;
      padding-bottom: 1rem;
      border-bottom: 2px solid var(--border);
    }
    
    h1 { color: var(--primary); margin-bottom: 0.5rem; }
    h2 { color: var(--text); margin: 2rem 0 1rem; border-bottom: 1px solid var(--border); padding-bottom: 0.5rem; }
    h3 { color: var(--text); margin: 1.5rem 0 0.75rem; }
    
    .subtitle { color: var(--text-muted); }
    .source { color: var(--text-muted); font-size: 0.9rem; }
    code { background: var(--border); padding: 0.2rem 0.4rem; border-radius: 4px; font-size: 0.85rem; }
    
    .card {
      background: var(--card-bg);
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
      padding: 1.5rem;
      margin-bottom: 1.5rem;
    }
    
    .summary-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 1rem;
      margin-bottom: 1.5rem;
    }
    
    .metric {
      background: var(--card-bg);
      border-radius: 8px;
      padding: 1rem;
      text-align: center;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .metric-value { font-size: 2rem; font-weight: bold; color: var(--primary); }
    .metric-label { font-size: 0.85rem; color: var(--text-muted); }
    
    table {
      width: 100%;
      border-collapse: collapse;
      margin: 1rem 0;
    }
    
    th, td {
      padding: 0.75rem;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    
    th { background: var(--primary); color: white; font-weight: 600; }
    tr:hover { background: var(--bg); }
    
    .score-badge {
      display: inline-block;
      padding: 0.25rem 0.5rem;
      border-radius: 4px;
      font-weight: 600;
      color: white;
    }
    
    .score-high { background: var(--success); }
    .score-medium { background: var(--warning); }
    .score-low { background: var(--danger); }
    
    .chart-container {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
      gap: 1.5rem;
      margin: 1.5rem 0;
    }
    
    .chart-container img {
      max-width: 100%;
      height: auto;
      border-radius: 8px;
      box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    
    .status-passed { color: var(--success); }
    .status-failed { color: var(--danger); }
    
    .error-list { list-style: none; font-size: 0.9rem; }
    .error-list li { padding: 0.5rem; background: #fef2f2; margin: 0.25rem 0; border-radius: 4px; }
    """


def _generate_summary_html(report: ComparisonReport) -> str:
    """Generate HTML for summary section."""
    html = ["<section>", "<h2>Summary</h2>"]
    
    # Key metrics
    html.append("<div class='summary-grid'>")
    html.append(f"""
    <div class='metric'>
      <div class='metric-value'>{len(report.evaluations)}</div>
      <div class='metric-label'>Models Evaluated</div>
    </div>
    """)
    
    if report.best_model and report.best_score is not None and report.average_score is not None:
        html.append(f"""
        <div class='metric'>
          <div class='metric-value'>{report.best_score*100:.1f}%</div>
          <div class='metric-label'>Best Score</div>
        </div>
        <div class='metric'>
          <div class='metric-value'>{report.average_score*100:.1f}%</div>
          <div class='metric-label'>Average Score</div>
        </div>
        """)
    
    html.append("</div>")
    
    # Rankings table
    html.append("<div class='card'>")
    html.append("<h3>Model Rankings</h3>")
    html.append("<table>")
    html.append("<tr><th>Rank</th><th>Model</th><th>Schema</th><th>Structure</th><th>Semantic</th><th>Config</th><th>Overall</th></tr>")
    
    for i, result in enumerate(sorted(report.evaluations, key=lambda r: r.scores.overall_score, reverse=True), 1):
        score_class = "score-high" if result.scores.overall_score >= 0.8 else ("score-medium" if result.scores.overall_score >= 0.5 else "score-low")
        html.append(f"""
        <tr>
          <td>{i}</td>
          <td>{result.metadata.model_id}</td>
          <td>{result.scores.schema_compliance*100:.1f}%</td>
          <td>{result.scores.structural_accuracy*100:.1f}%</td>
          <td>{result.scores.semantic_accuracy*100:.1f}%</td>
          <td>{result.scores.config_accuracy*100:.1f}%</td>
          <td><span class='score-badge {score_class}'>{result.scores.overall_score*100:.1f}%</span></td>
        </tr>
        """)
    
    html.append("</table>")
    html.append("</div>")
    html.append("</section>")
    
    return "\n".join(html)


def _generate_charts_html(chart_paths: dict[str, Path], report_dir: Path) -> str:
    """Generate HTML for charts section."""
    html = ["<section>", "<h2>Visualizations</h2>", "<div class='chart-container'>"]
    
    for name, path in chart_paths.items():
        try:
            # Use relative path from report directory
            rel_path = path.relative_to(report_dir)
        except ValueError:
            rel_path = path
        
        display_name = name.replace("_", " ").title()
        html.append(f"""
        <div>
          <h4>{display_name}</h4>
          <img src='{rel_path}' alt='{display_name}'>
        </div>
        """)
    
    html.append("</div>")
    html.append("</section>")
    
    return "\n".join(html)


def _generate_details_html(report: ComparisonReport) -> str:
    """Generate HTML for detailed results section."""
    html = ["<section>", "<h2>Detailed Results</h2>"]
    
    for result in report.evaluations:
        html.append("<div class='card'>")
        html.append(f"<h3>{result.metadata.model_id}</h3>")
        html.append(f"<p>Provider: {result.metadata.provider}</p>")
        
        # Schema validation
        if result.schema_validation.is_valid:
            html.append("<p class='status-passed'>✓ Schema Validation: PASSED</p>")
        else:
            html.append(f"<p class='status-failed'>✗ Schema Validation: FAILED ({result.schema_validation.error_count} errors)</p>")
            html.append("<ul class='error-list'>")
            for error in result.schema_validation.errors[:5]:
                html.append(f"<li><code>{error.path}</code>: {error.message}</li>")
            if result.schema_validation.error_count > 5:
                html.append(f"<li>... and {result.schema_validation.error_count - 5} more errors</li>")
            html.append("</ul>")
        
        # Section details table
        if result.sections:
            html.append("<h4>Section Analysis</h4>")
            html.append("<table>")
            html.append("<tr><th>Source Section</th><th>Model Section</th><th>Name Match</th><th>Fields Matched</th><th>Score</th></tr>")
            
            for section in result.sections:
                model_name = section.model_section_name or "<em>MISSING</em>"
                score_class = "score-high" if section.section_score >= 0.8 else ("score-medium" if section.section_score >= 0.5 else "score-low")
                html.append(f"""
                <tr>
                  <td>{section.source_section_name}</td>
                  <td>{model_name}</td>
                  <td>{section.section_name_similarity*100:.0f}%</td>
                  <td>{section.matched_fields}/{section.source_field_count}</td>
                  <td><span class='score-badge {score_class}'>{section.section_score*100:.0f}%</span></td>
                </tr>
                """)
            
            html.append("</table>")
        
        html.append("</div>")
    
    html.append("</section>")
    
    return "\n".join(html)

