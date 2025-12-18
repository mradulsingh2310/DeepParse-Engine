"""
Pydantic models for structured evaluation results.

These models capture the full evaluation output including schema validation,
deterministic field comparison, and LLM semantic analysis scores.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class MatchType(str, Enum):
    """Type of match between source and model fields."""
    EXACT = "exact"
    PARTIAL = "partial"
    MISSING = "missing"
    EXTRA = "extra"


class ValidationError(BaseModel):
    """Schema validation error with path information."""
    path: str = Field(description="JSON path to the error location")
    message: str = Field(description="Error message")
    value: str | None = Field(default=None, description="The invalid value")


class FieldConfigComparison(BaseModel):
    """Comparison results for field configuration boolean/enum fields."""
    mandatory: bool = Field(description="mandatory field match")
    notes_enabled: bool = Field(description="notes_enabled match")
    notes_required_for_all_options: bool = Field(description="notes_required_for_all_options match")
    notes_required_for_selected_options: float = Field(
        description="Similarity score for notes_required_for_selected_options (0.0-1.0)"
    )
    attachments_enabled: bool = Field(description="attachments_enabled match")
    attachments_required_for_all_options: bool = Field(
        description="attachments_required_for_all_options match"
    )
    attachments_required_for_selected_options: float = Field(
        description="Similarity score for attachments_required_for_selected_options (0.0-1.0)"
    )
    can_create_work_order: bool = Field(description="can_create_work_order match")
    work_order_category: bool = Field(description="work_order_category enum match")
    work_order_sub_category: bool = Field(description="work_order_sub_category enum match")


class FieldEvaluation(BaseModel):
    """Evaluation result for a single field comparison."""
    source_field_id: int = Field(description="Field ID from source of truth")
    model_field_id: int | None = Field(description="Field ID from model output (None if missing)")
    source_name: str = Field(description="Field name from source of truth")
    model_name: str | None = Field(description="Field name from model output")
    match_type: MatchType = Field(description="Type of match")
    
    # Semantic scores (from LLM)
    name_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic similarity of field names (0.0-1.0)"
    )
    options_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic similarity of options (0.0-1.0)"
    )
    
    # Deterministic scores
    rating_type_match: bool = Field(default=False, description="Exact rating_type enum match")
    options_exact_match: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Case-insensitive options list match (0.0-1.0)"
    )
    
    # Configuration comparison
    config_comparison: FieldConfigComparison | None = Field(
        default=None,
        description="Detailed configuration field comparison"
    )
    
    # Reasoning from LLM
    reasoning: str | None = Field(default=None, description="LLM reasoning for the evaluation")
    
    # Computed scores
    config_score: float = Field(default=0.0, description="Aggregate config match score (0.0-1.0)")
    overall_score: float = Field(default=0.0, description="Weighted overall field score (0.0-1.0)")


class SectionEvaluation(BaseModel):
    """Evaluation result for a section comparison."""
    source_section_name: str = Field(description="Section name from source of truth")
    model_section_name: str | None = Field(description="Section name from model output")
    section_name_similarity: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Semantic similarity of section names"
    )
    
    source_field_count: int = Field(description="Number of fields in source section")
    model_field_count: int = Field(description="Number of fields in model section")
    field_count_match: bool = Field(description="Whether field counts match")
    
    matched_fields: int = Field(default=0, description="Number of successfully matched fields")
    missing_fields: int = Field(default=0, description="Fields in source but not in model")
    extra_fields: int = Field(default=0, description="Fields in model but not in source")
    
    fields: list[FieldEvaluation] = Field(default_factory=list, description="Field evaluations")
    section_score: float = Field(default=0.0, description="Aggregate section score (0.0-1.0)")


class SchemaValidationResult(BaseModel):
    """Result of schema validation."""
    is_valid: bool = Field(description="Whether the JSON is valid against schema")
    errors: list[ValidationError] = Field(default_factory=list, description="Validation errors")
    error_count: int = Field(default=0, description="Total number of errors")
    compliance_score: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Schema compliance score (1.0 = fully compliant)"
    )


class AggregateScores(BaseModel):
    """Aggregate scores across all dimensions."""
    schema_compliance: float = Field(description="Schema validation compliance (0.0-1.0)")
    structural_accuracy: float = Field(description="Section/field structure accuracy (0.0-1.0)")
    semantic_accuracy: float = Field(description="LLM semantic similarity score (0.0-1.0)")
    config_accuracy: float = Field(description="Configuration fields accuracy (0.0-1.0)")
    overall_score: float = Field(description="Weighted overall score (0.0-1.0)")


class ModelMetadata(BaseModel):
    """Metadata about the model that generated the output."""
    provider: str = Field(description="Provider name (e.g., bedrock, deepseek)")
    model_id: str = Field(description="Model identifier")
    supporting_model_id: str | None = Field(default=None, description="Supporting model if any")


class EvaluationResult(BaseModel):
    """Complete evaluation result for a single model output."""
    # Identification
    source_file: str = Field(description="Path to source of truth file")
    model_file: str = Field(description="Path to model output file")
    metadata: ModelMetadata = Field(description="Model metadata")
    
    # Schema validation
    schema_validation: SchemaValidationResult = Field(description="Schema validation results")
    
    # Section evaluations
    total_source_sections: int = Field(description="Total sections in source")
    total_model_sections: int = Field(description="Total sections in model")
    sections: list[SectionEvaluation] = Field(default_factory=list, description="Section evaluations")
    
    # Aggregate scores
    scores: AggregateScores = Field(description="Aggregate scores")
    
    # Metadata
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Evaluation timestamp"
    )
    evaluation_duration_ms: int | None = Field(
        default=None,
        description="Time taken for evaluation in milliseconds"
    )


class ComparisonReport(BaseModel):
    """Report comparing multiple models against a source of truth."""
    source_file: str = Field(description="Path to source of truth file")
    evaluations: list[EvaluationResult] = Field(
        default_factory=list,
        description="Evaluation results for each model"
    )
    
    # Ranking
    ranked_models: list[str] = Field(
        default_factory=list,
        description="Model IDs ranked by overall score (best first)"
    )
    
    # Summary statistics
    best_model: str | None = Field(default=None, description="Model with highest overall score")
    best_score: float | None = Field(default=None, description="Highest overall score")
    average_score: float | None = Field(default=None, description="Average score across all models")
    
    timestamp: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
        description="Report generation timestamp"
    )

