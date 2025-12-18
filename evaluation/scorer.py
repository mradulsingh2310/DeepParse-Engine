"""
Aggregate Scoring Logic

Combines scores from schema validation, deterministic comparison,
and LLM semantic evaluation into weighted overall scores.
"""

from __future__ import annotations

from evaluation.models import (
    FieldEvaluation,
    SectionEvaluation,
    SchemaValidationResult,
    AggregateScores,
    MatchType,
)


# Scoring weights for field-level calculation
FIELD_WEIGHTS = {
    "name_similarity": 0.20,       # LLM semantic
    "options_match": 0.15,         # LLM + normalized
    "rating_type": 0.15,           # Exact match
    "mandatory": 0.10,             # Exact match
    "notes_config": 0.10,          # Avg of 3 boolean fields
    "attachments_config": 0.10,    # Avg of 3 boolean fields  
    "work_order_config": 0.20,     # Avg of 3 fields
}

# Scoring weights for aggregate calculation
AGGREGATE_WEIGHTS = {
    "schema_compliance": 0.15,
    "structural_accuracy": 0.20,
    "semantic_accuracy": 0.30,
    "config_accuracy": 0.35,
}


def calculate_field_score(field_eval: FieldEvaluation) -> float:
    """
    Calculate weighted overall score for a single field.
    
    Uses weights defined in FIELD_WEIGHTS.
    """
    if field_eval.match_type == MatchType.MISSING:
        return 0.0
    
    # Name similarity (LLM)
    name_score = field_eval.name_similarity
    
    # Options match (use semantic if available, else deterministic)
    options_score = max(field_eval.options_similarity, field_eval.options_exact_match)
    
    # Rating type exact match
    rating_type_score = 1.0 if field_eval.rating_type_match else 0.0
    
    # Get config scores
    config = field_eval.config_comparison
    if config:
        # Mandatory
        mandatory_score = 1.0 if config.mandatory else 0.0
        
        # Notes config (avg of 3 fields)
        notes_booleans = [config.notes_enabled, config.notes_required_for_all_options]
        notes_boolean_score = sum(1.0 for b in notes_booleans if b) / len(notes_booleans)
        notes_score = (notes_boolean_score + config.notes_required_for_selected_options) / 2
        
        # Attachments config (avg of 3 fields)
        attach_booleans = [config.attachments_enabled, config.attachments_required_for_all_options]
        attach_boolean_score = sum(1.0 for b in attach_booleans if b) / len(attach_booleans)
        attach_score = (attach_boolean_score + config.attachments_required_for_selected_options) / 2
        
        # Work order config (avg of 3 fields)
        work_order_fields = [
            config.can_create_work_order,
            config.work_order_category,
            config.work_order_sub_category,
        ]
        work_order_score = sum(1.0 for b in work_order_fields if b) / len(work_order_fields)
    else:
        mandatory_score = 0.0
        notes_score = 0.0
        attach_score = 0.0
        work_order_score = 0.0
    
    # Calculate weighted score
    score = (
        FIELD_WEIGHTS["name_similarity"] * name_score +
        FIELD_WEIGHTS["options_match"] * options_score +
        FIELD_WEIGHTS["rating_type"] * rating_type_score +
        FIELD_WEIGHTS["mandatory"] * mandatory_score +
        FIELD_WEIGHTS["notes_config"] * notes_score +
        FIELD_WEIGHTS["attachments_config"] * attach_score +
        FIELD_WEIGHTS["work_order_config"] * work_order_score
    )
    
    return round(score, 4)


def calculate_section_score(section_eval: SectionEvaluation) -> float:
    """
    Calculate aggregate score for a section.
    
    Combines field scores with section-level metrics.
    """
    if not section_eval.fields:
        return 0.0
    
    # Calculate average field score
    field_scores = [f.overall_score for f in section_eval.fields]
    avg_field_score = sum(field_scores) / len(field_scores) if field_scores else 0.0
    
    # Section name similarity bonus
    name_bonus = section_eval.section_name_similarity * 0.1
    
    # Field count match bonus
    count_bonus = 0.05 if section_eval.field_count_match else 0.0
    
    # Penalty for missing/extra fields
    total_fields = section_eval.source_field_count
    if total_fields > 0:
        missing_penalty = (section_eval.missing_fields / total_fields) * 0.1
        extra_penalty = (section_eval.extra_fields / max(section_eval.model_field_count, 1)) * 0.05
    else:
        missing_penalty = 0.0
        extra_penalty = 0.0
    
    score = avg_field_score + name_bonus + count_bonus - missing_penalty - extra_penalty
    return max(0.0, min(1.0, round(score, 4)))


def calculate_aggregate_scores(
    schema_result: SchemaValidationResult,
    section_evaluations: list[SectionEvaluation],
) -> AggregateScores:
    """
    Calculate aggregate scores across all dimensions.
    
    Args:
        schema_result: Schema validation result
        section_evaluations: List of section evaluations
        
    Returns:
        AggregateScores with all metrics
    """
    # Schema compliance
    schema_compliance = schema_result.compliance_score
    
    # Structural accuracy (sections and fields matching)
    if section_evaluations:
        matched_sections = sum(
            1 for s in section_evaluations 
            if s.model_section_name is not None
        )
        total_sections = len(section_evaluations)
        section_match_ratio = matched_sections / total_sections if total_sections > 0 else 0.0
        
        total_source_fields = sum(s.source_field_count for s in section_evaluations)
        total_matched_fields = sum(s.matched_fields for s in section_evaluations)
        field_match_ratio = total_matched_fields / total_source_fields if total_source_fields > 0 else 0.0
        
        structural_accuracy = (section_match_ratio + field_match_ratio) / 2
    else:
        structural_accuracy = 0.0
    
    # Semantic accuracy (name and options similarity from LLM)
    if section_evaluations:
        all_fields = [f for s in section_evaluations for f in s.fields]
        if all_fields:
            name_similarities = [f.name_similarity for f in all_fields if f.match_type != MatchType.MISSING]
            option_similarities = [f.options_similarity for f in all_fields if f.match_type != MatchType.MISSING]
            
            avg_name_sim = sum(name_similarities) / len(name_similarities) if name_similarities else 0.0
            avg_option_sim = sum(option_similarities) / len(option_similarities) if option_similarities else 0.0
            
            semantic_accuracy = (avg_name_sim + avg_option_sim) / 2
        else:
            semantic_accuracy = 0.0
    else:
        semantic_accuracy = 0.0
    
    # Config accuracy (boolean/enum fields)
    if section_evaluations:
        all_fields = [f for s in section_evaluations for f in s.fields]
        if all_fields:
            config_scores = [f.config_score for f in all_fields if f.config_score > 0]
            config_accuracy = sum(config_scores) / len(config_scores) if config_scores else 0.0
        else:
            config_accuracy = 0.0
    else:
        config_accuracy = 0.0
    
    # Overall score (weighted combination)
    overall_score = (
        AGGREGATE_WEIGHTS["schema_compliance"] * schema_compliance +
        AGGREGATE_WEIGHTS["structural_accuracy"] * structural_accuracy +
        AGGREGATE_WEIGHTS["semantic_accuracy"] * semantic_accuracy +
        AGGREGATE_WEIGHTS["config_accuracy"] * config_accuracy
    )
    
    return AggregateScores(
        schema_compliance=round(schema_compliance, 4),
        structural_accuracy=round(structural_accuracy, 4),
        semantic_accuracy=round(semantic_accuracy, 4),
        config_accuracy=round(config_accuracy, 4),
        overall_score=round(overall_score, 4),
    )


def score_all_fields(section_evaluations: list[SectionEvaluation]) -> list[SectionEvaluation]:
    """
    Calculate and update scores for all fields and sections.
    
    Args:
        section_evaluations: List of section evaluations
        
    Returns:
        Updated section evaluations with scores
    """
    for section_eval in section_evaluations:
        # Score each field
        for field_eval in section_eval.fields:
            field_eval.overall_score = calculate_field_score(field_eval)
        
        # Score the section
        section_eval.section_score = calculate_section_score(section_eval)
    
    return section_evaluations

