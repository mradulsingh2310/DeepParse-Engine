"""
Merge utilities for chunked image processing.

When documents are processed in chunks (e.g., 2 pages at a time),
this module provides functions to merge the partial JSON responses
into a single coherent result.
"""

from typing import Any

from src.utils.logger import log


def merge_section_responses(responses: list[dict]) -> dict:
    """
    Merge multiple partial section responses into one complete response.
    
    Args:
        responses: List of partial response dicts, each containing a Section structure
        
    Returns:
        Merged Section dict with all sections/fields combined and field IDs regenerated
    """
    if not responses:
        return {}
    
    if len(responses) == 1:
        # Single response, just regenerate field IDs
        result = responses[0].copy()
        _regenerate_field_ids(result, [1])
        return result
    
    # Start with the first response as base
    merged = _deep_copy_dict(responses[0])
    
    # Merge subsequent responses
    for i, response in enumerate(responses[1:], start=2):
        log(f"Merging chunk {i} of {len(responses)}...")
        merged = _merge_sections(merged, response)
    
    # Regenerate field IDs sequentially
    log("Regenerating field IDs...")
    _regenerate_field_ids(merged, [1])
    
    return merged


def _deep_copy_dict(obj: Any) -> Any:
    """Deep copy a dict/list structure."""
    if isinstance(obj, dict):
        return {k: _deep_copy_dict(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_deep_copy_dict(item) for item in obj]
    return obj


def _merge_sections(base: dict, incoming: dict) -> dict:
    """
    Recursively merge two section dicts by name.
    
    Rules:
    - If a section with the same name exists in both, merge their children
    - Sections unique to incoming are appended
    - Fields in matching sections are appended (no deduplication by name)
    
    Args:
        base: The base section dict (accumulated result)
        incoming: The incoming section dict to merge
        
    Returns:
        Merged section dict
    """
    # If incoming is empty or not a dict, return base
    if not incoming or not isinstance(incoming, dict):
        return base
    
    # If base is empty, return incoming
    if not base:
        return _deep_copy_dict(incoming)
    
    # Create result based on base
    result = _deep_copy_dict(base)
    
    # Merge top-level fields like name, display_type (keep base values)
    # These should be consistent across chunks for the same document
    
    # Merge child sections
    base_sections = result.get("sections", [])
    incoming_sections = incoming.get("sections", [])
    
    if incoming_sections:
        # Build a map of base sections by name for efficient lookup
        base_section_map: dict[str, int] = {}
        for idx, section in enumerate(base_sections):
            name = section.get("name", "")
            if name:
                base_section_map[name] = idx
        
        for inc_section in incoming_sections:
            inc_name = inc_section.get("name", "")
            
            if inc_name and inc_name in base_section_map:
                # Section exists in base - merge recursively
                base_idx = base_section_map[inc_name]
                base_sections[base_idx] = _merge_sections(
                    base_sections[base_idx], 
                    inc_section
                )
            else:
                # New section - append
                base_sections.append(_deep_copy_dict(inc_section))
        
        result["sections"] = base_sections
    
    # Merge fields (append incoming fields to base fields)
    base_fields = result.get("fields", [])
    incoming_fields = incoming.get("fields", [])
    
    if incoming_fields:
        # Simply append incoming fields - they'll get new IDs during regeneration
        for field in incoming_fields:
            base_fields.append(_deep_copy_dict(field))
        result["fields"] = base_fields
    
    return result


def _regenerate_field_ids(section: dict, counter: list[int]) -> None:
    """
    Recursively regenerate sequential field IDs across all sections.
    
    Uses a mutable list as counter to maintain state across recursive calls.
    
    Args:
        section: Section dict to process (modified in place)
        counter: Mutable list containing [current_id] - starts at [1]
    """
    # Process fields in this section
    fields = section.get("fields", [])
    for field in fields:
        if isinstance(field, dict):
            field["id"] = counter[0]
            counter[0] += 1
    
    # Recursively process child sections
    child_sections = section.get("sections", [])
    for child in child_sections:
        if isinstance(child, dict):
            _regenerate_field_ids(child, counter)

