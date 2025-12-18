"""
Level 2: Deterministic Field Comparison

Compares fields between model output and source of truth using
exact matching for boolean/enum fields and normalized comparison for lists.
"""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from evaluation.models import (
    FieldEvaluation,
    SectionEvaluation,
    FieldConfigComparison,
    MatchType,
)


def load_json_file(file_path: str | Path) -> dict:
    """Load JSON from file path."""
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def extract_sections(json_data: dict) -> list[dict]:
    """
    Extract sections from inspection template JSON.
    
    Returns list of section dicts with fields.
    """
    sections: list[dict] = []
    
    # Remove metadata
    data = {k: v for k, v in json_data.items() if k != "_metadata"}
    
    versions = data.get("versions", [])
    if not versions:
        return sections
    
    # Use first version
    structure = versions[0].get("structure", {})
    
    # Collect all sections (could be nested)
    def collect_sections(section: dict) -> None:
        fields = section.get("fields", [])
        subsections = section.get("sections", [])
        
        # If this section has fields, add it
        if fields:
            sections.append({
                "name": section.get("name", "Unknown"),
                "display_type": section.get("display_type", ""),
                "fields": fields,
            })
        
        # Recurse into subsections
        for subsection in subsections:
            collect_sections(subsection)
    
    collect_sections(structure)
    return sections


def normalize_string(s: str) -> str:
    """Normalize string for comparison (lowercase, strip whitespace)."""
    return s.lower().strip()


def normalize_list(lst: list[str]) -> set[str]:
    """Normalize list of strings to set for comparison."""
    return {normalize_string(item) for item in lst}


def string_similarity(s1: str, s2: str) -> float:
    """
    Calculate string similarity using SequenceMatcher.
    Returns value between 0.0 and 1.0.
    """
    if not s1 or not s2:
        return 0.0
    return SequenceMatcher(None, normalize_string(s1), normalize_string(s2)).ratio()


def list_similarity(list1: list[str], list2: list[str]) -> float:
    """
    Calculate similarity between two lists of strings.
    Uses set intersection for case-insensitive comparison.
    """
    if not list1 and not list2:
        return 1.0
    if not list1 or not list2:
        return 0.0
    
    set1 = normalize_list(list1)
    set2 = normalize_list(list2)
    
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def ordered_list_similarity(list1: list[str], list2: list[str]) -> float:
    """
    Calculate similarity between two ordered lists.
    Considers both content and order.
    """
    if not list1 and not list2:
        return 1.0
    if not list1 or not list2:
        return 0.0
    
    # Normalize both lists
    norm1 = [normalize_string(item) for item in list1]
    norm2 = [normalize_string(item) for item in list2]
    
    # Check if they're exactly equal
    if norm1 == norm2:
        return 1.0
    
    # Check set equality (content match, order may differ)
    if set(norm1) == set(norm2):
        return 0.9  # Slight penalty for order mismatch
    
    # Calculate Jaccard similarity for partial matches
    set1 = set(norm1)
    set2 = set(norm2)
    intersection = len(set1 & set2)
    union = len(set1 | set2)
    
    return intersection / union if union > 0 else 0.0


def compare_field_config(source_field: dict, model_field: dict) -> FieldConfigComparison:
    """
    Compare configuration fields between source and model.
    """
    return FieldConfigComparison(
        mandatory=source_field.get("mandatory", False) == model_field.get("mandatory", False),
        notes_enabled=source_field.get("notes_enabled", False) == model_field.get("notes_enabled", False),
        notes_required_for_all_options=source_field.get("notes_required_for_all_options", False) == model_field.get("notes_required_for_all_options", False),
        notes_required_for_selected_options=list_similarity(
            source_field.get("notes_required_for_selected_options", []),
            model_field.get("notes_required_for_selected_options", [])
        ),
        attachments_enabled=source_field.get("attachments_enabled", False) == model_field.get("attachments_enabled", False),
        attachments_required_for_all_options=source_field.get("attachments_required_for_all_options", False) == model_field.get("attachments_required_for_all_options", False),
        attachments_required_for_selected_options=list_similarity(
            source_field.get("attachments_required_for_selected_options", []),
            model_field.get("attachments_required_for_selected_options", [])
        ),
        can_create_work_order=source_field.get("can_create_work_order", False) == model_field.get("can_create_work_order", False),
        work_order_category=source_field.get("work_order_category", "") == model_field.get("work_order_category", ""),
        work_order_sub_category=source_field.get("work_order_sub_category", "") == model_field.get("work_order_sub_category", ""),
    )


def calculate_config_score(config: FieldConfigComparison) -> float:
    """
    Calculate aggregate config score from individual matches.
    """
    boolean_fields = [
        config.mandatory,
        config.notes_enabled,
        config.notes_required_for_all_options,
        config.attachments_enabled,
        config.attachments_required_for_all_options,
        config.can_create_work_order,
        config.work_order_category,
        config.work_order_sub_category,
    ]
    
    # Count boolean matches
    boolean_score = sum(1 for b in boolean_fields if b) / len(boolean_fields)
    
    # Include list similarity scores
    list_scores = [
        config.notes_required_for_selected_options,
        config.attachments_required_for_selected_options,
    ]
    list_score = sum(list_scores) / len(list_scores)
    
    # Weighted combination (boolean fields more important)
    return 0.7 * boolean_score + 0.3 * list_score


def match_sections(source_sections: list[dict], model_sections: list[dict]) -> list[tuple[dict, dict | None]]:
    """
    Match source sections to model sections by name similarity.
    
    Returns list of tuples (source_section, matched_model_section or None).
    """
    matches = []
    used_model_indices = set()
    
    for source_section in source_sections:
        source_name = source_section.get("name", "")
        best_match = None
        best_score = 0.0
        best_idx = -1
        
        for idx, model_section in enumerate(model_sections):
            if idx in used_model_indices:
                continue
            
            model_name = model_section.get("name", "")
            score = string_similarity(source_name, model_name)
            
            if score > best_score and score > 0.5:  # Threshold for matching
                best_score = score
                best_match = model_section
                best_idx = idx
        
        if best_idx >= 0:
            used_model_indices.add(best_idx)
        
        matches.append((source_section, best_match))
    
    return matches


def match_fields(source_fields: list[dict], model_fields: list[dict]) -> list[tuple[dict, dict | None, float]]:
    """
    Match source fields to model fields by name similarity and ID proximity.
    
    Returns list of tuples (source_field, matched_model_field or None, similarity_score).
    """
    matches = []
    used_model_indices = set()
    
    for source_field in source_fields:
        source_name = source_field.get("name", "")
        source_id = source_field.get("id", 0)
        best_match = None
        best_score = 0.0
        best_idx = -1
        
        for idx, model_field in enumerate(model_fields):
            if idx in used_model_indices:
                continue
            
            model_name = model_field.get("name", "")
            model_id = model_field.get("id", 0)
            
            # Calculate name similarity
            name_score = string_similarity(source_name, model_name)
            
            # Bonus for matching IDs
            id_bonus = 0.1 if source_id == model_id else 0.0
            
            total_score = min(1.0, name_score + id_bonus)
            
            if total_score > best_score and name_score > 0.3:  # Threshold
                best_score = total_score
                best_match = model_field
                best_idx = idx
        
        if best_idx >= 0:
            used_model_indices.add(best_idx)
        
        matches.append((source_field, best_match, best_score))
    
    return matches


def compare_field(source_field: dict, model_field: dict | None, name_similarity: float = 0.0) -> FieldEvaluation:
    """
    Compare a source field against a model field.
    """
    if model_field is None:
        return FieldEvaluation(
            source_field_id=source_field.get("id", 0),
            model_field_id=None,
            source_name=source_field.get("name", ""),
            model_name=None,
            match_type=MatchType.MISSING,
            name_similarity=0.0,
            options_similarity=0.0,
            rating_type_match=False,
            options_exact_match=0.0,
            config_comparison=None,
            config_score=0.0,
            overall_score=0.0,
        )
    
    # Compare rating types
    source_rating = source_field.get("rating_type", "")
    model_rating = model_field.get("rating_type", "")
    rating_type_match = source_rating == model_rating
    
    # Compare options
    source_options = source_field.get("options", [])
    model_options = model_field.get("options", [])
    options_exact_match = ordered_list_similarity(source_options, model_options)
    
    # Compare configuration
    config_comparison = compare_field_config(source_field, model_field)
    config_score = calculate_config_score(config_comparison)
    
    # Calculate name similarity if not provided
    if name_similarity == 0.0:
        name_similarity = string_similarity(
            source_field.get("name", ""),
            model_field.get("name", "")
        )
    
    return FieldEvaluation(
        source_field_id=source_field.get("id", 0),
        model_field_id=model_field.get("id"),
        source_name=source_field.get("name", ""),
        model_name=model_field.get("name"),
        match_type=MatchType.EXACT if name_similarity > 0.9 else MatchType.PARTIAL,
        name_similarity=name_similarity,
        options_similarity=options_exact_match,  # Will be updated by LLM
        rating_type_match=rating_type_match,
        options_exact_match=options_exact_match,
        config_comparison=config_comparison,
        config_score=config_score,
        overall_score=0.0,  # Will be calculated by scorer
    )


def compare_section(source_section: dict, model_section: dict | None) -> SectionEvaluation:
    """
    Compare a source section against a model section.
    """
    source_name = source_section.get("name", "")
    source_fields = source_section.get("fields", [])
    
    if model_section is None:
        return SectionEvaluation(
            source_section_name=source_name,
            model_section_name=None,
            section_name_similarity=0.0,
            source_field_count=len(source_fields),
            model_field_count=0,
            field_count_match=False,
            matched_fields=0,
            missing_fields=len(source_fields),
            extra_fields=0,
            fields=[compare_field(f, None) for f in source_fields],
            section_score=0.0,
        )
    
    model_name = model_section.get("name", "")
    model_fields = model_section.get("fields", [])
    
    # Match fields
    field_matches = match_fields(source_fields, model_fields)
    
    # Create field evaluations
    field_evaluations = []
    matched_count = 0
    
    for source_field, matched_model_field, similarity in field_matches:
        eval_result = compare_field(source_field, matched_model_field, similarity)
        field_evaluations.append(eval_result)
        if matched_model_field is not None:
            matched_count += 1
    
    # Calculate missing and extra fields
    missing_count = len(source_fields) - matched_count
    extra_count = max(0, len(model_fields) - matched_count)
    
    # Section name similarity
    name_similarity = string_similarity(source_name, model_name)
    
    return SectionEvaluation(
        source_section_name=source_name,
        model_section_name=model_name,
        section_name_similarity=name_similarity,
        source_field_count=len(source_fields),
        model_field_count=len(model_fields),
        field_count_match=len(source_fields) == len(model_fields),
        matched_fields=matched_count,
        missing_fields=missing_count,
        extra_fields=extra_count,
        fields=field_evaluations,
        section_score=0.0,  # Will be calculated by scorer
    )


def compare_templates(
    source_json: dict,
    model_json: dict,
) -> list[SectionEvaluation]:
    """
    Compare two inspection templates and return section evaluations.
    
    Args:
        source_json: Source of truth JSON
        model_json: Model output JSON
        
    Returns:
        List of SectionEvaluation for each source section
    """
    source_sections = extract_sections(source_json)
    model_sections = extract_sections(model_json)
    
    # Match sections
    section_matches = match_sections(source_sections, model_sections)
    
    # Compare each section
    section_evaluations = []
    for source_section, model_section in section_matches:
        evaluation = compare_section(source_section, model_section)
        section_evaluations.append(evaluation)
    
    return section_evaluations


def compare_templates_from_files(
    source_path: str | Path,
    model_path: str | Path,
) -> list[SectionEvaluation]:
    """
    Load and compare two inspection templates from files.
    """
    source_json = load_json_file(source_path)
    model_json = load_json_file(model_path)
    
    return compare_templates(source_json, model_json)

