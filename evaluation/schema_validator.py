"""
Level 1: Schema Validation

Validates model output JSON against the InspectionTemplate Pydantic schema.
Captures all validation errors with paths for downstream processing.
"""

from __future__ import annotations

import json
from pathlib import Path
from pydantic import ValidationError as PydanticValidationError

from src.schemas.inspection import InspectionTemplate
from evaluation.models import SchemaValidationResult, ValidationError


def validate_schema(json_data: dict) -> SchemaValidationResult:
    """
    Validate JSON data against the InspectionTemplate schema.
    
    Args:
        json_data: Dictionary containing the model output JSON
        
    Returns:
        SchemaValidationResult with validation status and errors
    """
    errors: list[ValidationError] = []
    
    # Remove metadata field if present (added by our extraction process)
    data_to_validate = {k: v for k, v in json_data.items() if k != "_metadata"}
    
    try:
        InspectionTemplate.model_validate(data_to_validate)
        return SchemaValidationResult(
            is_valid=True,
            errors=[],
            error_count=0,
            compliance_score=1.0
        )
    except PydanticValidationError as e:
        for error in e.errors():
            # Build the path string from error location
            path_parts = [str(p) for p in error.get("loc", [])]
            path = ".".join(path_parts) if path_parts else "root"
            
            # Get the invalid value if available
            input_value = error.get("input")
            value_str = None
            if input_value is not None:
                try:
                    if isinstance(input_value, (dict, list)):
                        value_str = json.dumps(input_value)[:100] + "..." if len(json.dumps(input_value)) > 100 else json.dumps(input_value)
                    else:
                        value_str = str(input_value)[:100]
                except Exception:
                    value_str = "<unable to serialize>"
            
            errors.append(ValidationError(
                path=path,
                message=error.get("msg", "Unknown validation error"),
                value=value_str
            ))
        
        # Calculate compliance score based on error count
        # Rough heuristic: each error reduces compliance
        # Cap at 0.0 for many errors
        total_fields = _count_total_fields(json_data)
        compliance = max(0.0, 1.0 - (len(errors) / max(total_fields, 1)))
        
        return SchemaValidationResult(
            is_valid=False,
            errors=errors,
            error_count=len(errors),
            compliance_score=compliance
        )


def validate_schema_from_file(file_path: str | Path) -> SchemaValidationResult:
    """
    Load and validate a JSON file against the schema.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        SchemaValidationResult with validation status and errors
    """
    path = Path(file_path)
    
    if not path.exists():
        return SchemaValidationResult(
            is_valid=False,
            errors=[ValidationError(path="file", message=f"File not found: {file_path}")],
            error_count=1,
            compliance_score=0.0
        )
    
    try:
        with open(path, "r", encoding="utf-8") as f:
            json_data = json.load(f)
    except json.JSONDecodeError as e:
        return SchemaValidationResult(
            is_valid=False,
            errors=[ValidationError(path="json", message=f"Invalid JSON: {str(e)}")],
            error_count=1,
            compliance_score=0.0
        )
    
    return validate_schema(json_data)


def _count_total_fields(json_data: dict) -> int:
    """
    Count total number of fields in the inspection template for compliance scoring.
    """
    count = 0
    
    try:
        versions = json_data.get("versions", [])
        for version in versions:
            structure = version.get("structure", {})
            count += _count_fields_in_section(structure)
    except Exception:
        return 1  # Return 1 to avoid division by zero
    
    return max(count, 1)


def _count_fields_in_section(section: dict) -> int:
    """Recursively count fields in a section."""
    count = len(section.get("fields", []))
    
    for subsection in section.get("sections", []):
        count += _count_fields_in_section(subsection)
    
    return count


def format_errors_for_llm(result: SchemaValidationResult) -> str:
    """
    Format validation errors for inclusion in LLM prompt.
    
    Args:
        result: Schema validation result
        
    Returns:
        Formatted string of errors
    """
    if result.is_valid:
        return "No schema validation errors found."
    
    lines = [f"Found {result.error_count} schema validation errors:"]
    for i, error in enumerate(result.errors[:20], 1):  # Limit to first 20 errors
        lines.append(f"  {i}. Path: {error.path}")
        lines.append(f"     Error: {error.message}")
        if error.value:
            lines.append(f"     Value: {error.value}")
    
    if result.error_count > 20:
        lines.append(f"  ... and {result.error_count - 20} more errors")
    
    return "\n".join(lines)

