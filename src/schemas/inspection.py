"""
Pydantic Schema Models for Inspection Templates.

Matches proto: accoladehq.api.resident.v1.maintenance.v1
"""

from __future__ import annotations
from enum import Enum
from typing import Any
from pydantic import BaseModel, ConfigDict, ValidationError
from pydantic_core import PydanticUndefined

from src.utils.logger import log


class SectionDisplayType(str, Enum):
    """Section display types - defines hierarchy."""
    UNSPECIFIED = "SECTION_DISPLAY_TYPE_UNSPECIFIED"  # Parent section with tabs
    TAB = "SECTION_DISPLAY_TYPE_TAB"  # Contains accordions
    ACCORDION = "SECTION_DISPLAY_TYPE_ACCORDION"  # Contains field sets
    FIELD_SET = "SECTION_DISPLAY_TYPE_FIELD_SET"  # Contains fields (leaf)


class RatingType(str, Enum):
    """Rating types for fields - MUST be specified (not UNSPECIFIED)."""
    CHECKBOX = "RATING_TYPE_CHECKBOX"
    RADIO = "RATING_TYPE_RADIO"
    SELECT = "RATING_TYPE_SELECT"


class MaintenanceCategory(str, Enum):
    """Work order categories."""
    UNSPECIFIED = "MAINTENANCE_CATEGORY_UNSPECIFIED"
    PLUMBING = "MAINTENANCE_CATEGORY_PLUMBING"
    ELECTRICAL = "MAINTENANCE_CATEGORY_ELECTRICAL"
    HVAC = "MAINTENANCE_CATEGORY_HVAC"
    PEST_CONTROL = "MAINTENANCE_CATEGORY_PEST_CONTROL"
    CLEANING = "MAINTENANCE_CATEGORY_CLEANING"
    CARPENTRY = "MAINTENANCE_CATEGORY_CARPENTRY"
    EXTERIOR = "MAINTENANCE_CATEGORY_EXTERIOR"
    APPLIANCE_REPAIR = "MAINTENANCE_CATEGORY_APPLIANCE_REPAIR"
    SECURITY = "MAINTENANCE_CATEGORY_SECURITY"
    PAINTING = "MAINTENANCE_CATEGORY_PAINTING"


class WorkOrderSubCategory(str, Enum):
    """Work order sub-categories from proto."""
    UNSPECIFIED = "WORK_ORDER_SUB_CATEGORY_UNSPECIFIED"
    # Plumbing
    PLUMBING_CLOGGED_DRAIN = "WORK_ORDER_SUB_CATEGORY_PLUMBING_CLOGGED_DRAIN"
    PLUMBING_FAUCET_LEAK = "WORK_ORDER_SUB_CATEGORY_PLUMBING_FAUCET_LEAK"
    PLUMBING_TOILET_REPAIR_REPLACEMENT = "WORK_ORDER_SUB_CATEGORY_PLUMBING_TOILET_REPAIR_REPLACEMENT"
    PLUMBING_PIPE_LEAK_BURST = "WORK_ORDER_SUB_CATEGORY_PLUMBING_PIPE_LEAK_BURST"
    PLUMBING_WATER_HEATER_REPAIR = "WORK_ORDER_SUB_CATEGORY_PLUMBING_WATER_HEATER_REPAIR"
    PLUMBING_SEWER_BACKUP = "WORK_ORDER_SUB_CATEGORY_PLUMBING_SEWER_BACKUP"
    PLUMBING_LOW_WATER_PRESSURE = "WORK_ORDER_SUB_CATEGORY_PLUMBING_LOW_WATER_PRESSURE"
    PLUMBING_SHOWER_TUB_ISSUES = "WORK_ORDER_SUB_CATEGORY_PLUMBING_SHOWER_TUB_ISSUES"
    PLUMBING_GARBAGE_DISPOSAL_REPAIR = "WORK_ORDER_SUB_CATEGORY_PLUMBING_GARBAGE_DISPOSAL_REPAIR"
    # Electrical
    ELECTRICAL_POWER_OUTAGE = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_POWER_OUTAGE"
    ELECTRICAL_LIGHT_FIXTURE = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_LIGHT_FIXTURE_INSTALLATION_REPAIR"
    ELECTRICAL_OUTLET_SWITCH = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_OUTLET_OR_SWITCH_NOT_WORKING"
    ELECTRICAL_CIRCUIT_BREAKER = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_CIRCUIT_BREAKER_TRIPPING"
    ELECTRICAL_WIRING = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_WIRING_ISSUES"
    ELECTRICAL_CEILING_FAN = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_CEILING_FAN_INSTALLATION_REPAIR"
    ELECTRICAL_SMOKE_DETECTOR = "WORK_ORDER_SUB_CATEGORY_ELECTRICAL_SMOKE_DETECTOR_ISSUE"
    # HVAC
    HVAC_AC_NOT_COOLING = "WORK_ORDER_SUB_CATEGORY_HVAC_AC_NOT_COOLING"
    HVAC_FURNACE_NOT_HEATING = "WORK_ORDER_SUB_CATEGORY_HVAC_FURNACE_NOT_HEATING"
    HVAC_THERMOSTAT = "WORK_ORDER_SUB_CATEGORY_HVAC_THERMOSTAT_MALFUNCTION"
    HVAC_AIR_FILTER = "WORK_ORDER_SUB_CATEGORY_HVAC_AIR_FILTER_REPLACEMENT"
    HVAC_VENT_CLEANING = "WORK_ORDER_SUB_CATEGORY_HVAC_VENT_CLEANING"
    # Pest Control
    PEST_RODENT = "WORK_ORDER_SUB_CATEGORY_PEST_CONTROL_RODENT_INFESTATION"
    PEST_COCKROACH = "WORK_ORDER_SUB_CATEGORY_PEST_CONTROL_COCKROACH_TREATMENT"
    PEST_PREVENTATIVE = "WORK_ORDER_SUB_CATEGORY_PEST_CONTROL_PREVENTATIVE_PEST_CONTROL"
    PEST_TERMITE = "WORK_ORDER_SUB_CATEGORY_PEST_CONTROL_TERMITE_CONTROL"
    PEST_BEE_WASP = "WORK_ORDER_SUB_CATEGORY_PEST_CONTROL_BEE_WASP_REMOVAL"
    # Carpentry
    CARPENTRY_DOOR = "WORK_ORDER_SUB_CATEGORY_CARPENTRY_DOOR_REPAIR_INSTALLATION"
    CARPENTRY_WINDOW_FRAME = "WORK_ORDER_SUB_CATEGORY_CARPENTRY_WINDOW_FRAME_REPAIR"
    CARPENTRY_CABINET = "WORK_ORDER_SUB_CATEGORY_CARPENTRY_CABINET_REPAIR"
    CARPENTRY_DRYWALL = "WORK_ORDER_SUB_CATEGORY_CARPENTRY_DRYWALL_REPAIR"
    CARPENTRY_FLOORBOARD = "WORK_ORDER_SUB_CATEGORY_CARPENTRY_FLOORBOARD_REPAIR"
    # Appliance
    APPLIANCE_REFRIGERATOR = "WORK_ORDER_SUB_CATEGORY_APPLIANCE_REPAIR_REFRIGERATOR_FAILURE"
    APPLIANCE_STOVE_OVEN = "WORK_ORDER_SUB_CATEGORY_APPLIANCE_REPAIR_STOVE_OVEN_MALFUNCTION"
    APPLIANCE_DISHWASHER = "WORK_ORDER_SUB_CATEGORY_APPLIANCE_REPAIR_DISHWASHER_FAILURE"
    # Security
    SECURITY_DOOR_LOCK = "WORK_ORDER_SUB_CATEGORY_SECURITY_DOOR_LOCK_REPAIR"
    SECURITY_SYSTEM = "WORK_ORDER_SUB_CATEGORY_SECURITY_SECURITY_SYSTEM_INTERCOM_MALFUNCTION"
    # Other
    PAINTING_MOLD = "WORK_ORDER_SUB_CATEGORY_PAINTING_MOLD_REMEDIATION"


class Field(BaseModel):
    """Inspection field - the smallest unit in the template tree."""
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    description: str | None = None
    mandatory: bool = False

    # Rating - MUST be specified (not UNSPECIFIED)
    rating_type: RatingType
    options: list[str] = []

    # Notes configuration
    notes_enabled: bool = False
    notes_required_for_all_options: bool = False
    notes_required_for_selected_options: list[str] = []

    # Attachments configuration
    attachments_enabled: bool = False
    attachments_required_for_all_options: bool = False
    attachments_required_for_selected_options: list[str] = []

    # Work order configuration
    can_create_work_order: bool = False
    work_order_category: MaintenanceCategory = MaintenanceCategory.UNSPECIFIED
    work_order_sub_category: WorkOrderSubCategory = WorkOrderSubCategory.UNSPECIFIED


class Section(BaseModel):
    """
    Inspection section - hierarchical structure.

    Hierarchy rules:
    - UNSPECIFIED: Root section, has child tabs (sections not empty, fields empty)
    - TAB: Has accordions (sections not empty, fields empty)
    - ACCORDION: Has field sets (sections not empty, fields empty)
    - FIELD_SET: Leaf node with fields (sections empty, fields not empty)
    """
    model_config = ConfigDict(extra="forbid")

    name: str
    display_type: SectionDisplayType = SectionDisplayType.UNSPECIFIED
    sections: list[Section] = []
    fields: list[Field] = []


class TemplateVersion(BaseModel):
    """A version of an inspection template."""
    model_config = ConfigDict(extra="forbid")

    version_id: int
    structure: Section


class InspectionTemplate(BaseModel):
    """
    Inspection template - ONLY contains inspection sections.
    
    Does NOT include: header info (project name, inspector, dates),
    footer info (signatures, comments), or any metadata.
    """
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    description: str | None = None
    property_ids: list[int] = []
    versions: list[TemplateVersion] = []
    created_at: str | None = None
    updated_at: str | None = None


# Rebuild for forward references
Section.model_rebuild()


# --- Lenient Validation Utilities ---

def _get_model_defaults(model: type[BaseModel]) -> dict[str, Any]:
    """Extract default values from a Pydantic model's field definitions."""
    
    defaults = {}
    for field_name, field_info in model.model_fields.items():
        if field_info.default is not PydanticUndefined:
            defaults[field_name] = field_info.default
        elif field_info.default_factory is not None:
            # default_factory is a no-arg callable that returns the default value
            try:
                defaults[field_name] = field_info.default_factory()  # type: ignore[call-arg]
            except TypeError:
                pass  # Skip if factory requires arguments
        # For required fields without defaults, we skip - will handle per-model
    return defaults


def _clean_dict_for_model(data: dict[str, Any], model: type[BaseModel]) -> tuple[dict[str, Any], set[str]]:
    """
    Clean a dictionary to only contain valid keys for a model.
    
    Returns:
        Tuple of (cleaned dict with only valid keys, set of removed keys)
    """
    valid_keys = set(model.model_fields.keys())
    cleaned = {k: v for k, v in data.items() if k in valid_keys}
    removed = set(data.keys()) - valid_keys
    return cleaned, removed


def _get_enum_valid_values(enum_class: type[Enum]) -> set[str]:
    """Get all valid string values for an enum."""
    return {e.value for e in enum_class}


# Mapping of field names to their enum types and defaults
FIELD_ENUM_CONFIG: dict[str, tuple[type[Enum], Any]] = {
    "rating_type": (RatingType, RatingType.RADIO),
    "work_order_category": (MaintenanceCategory, MaintenanceCategory.UNSPECIFIED),
    "work_order_sub_category": (WorkOrderSubCategory, WorkOrderSubCategory.UNSPECIFIED),
    "display_type": (SectionDisplayType, SectionDisplayType.UNSPECIFIED),
}


def _fix_enum_values(data: dict[str, Any], path: str) -> dict[str, Any]:
    """
    Fix invalid enum values by replacing with defaults.
    
    Args:
        data: Dictionary with potential enum fields
        path: Path for logging
        
    Returns:
        Dictionary with invalid enum values replaced by defaults
    """
    result = data.copy()
    
    for field_name, (enum_class, default_value) in FIELD_ENUM_CONFIG.items():
        if field_name in result:
            value = result[field_name]
            valid_values = _get_enum_valid_values(enum_class)
            
            if value not in valid_values:
                log(f"  [LENIENT] Invalid enum value at {path}.{field_name}: '{value}' -> using default '{default_value.value}'")
                result[field_name] = default_value.value
    
    return result


def validate_field_lenient(field_data: dict[str, Any], field_index: int, section_path: str) -> Field | None:
    """
    Validate a single field with lenient error handling.
    
    Strategy:
    1. Remove any extra/unknown fields
    2. Fix invalid enum values with defaults
    3. Apply defaults for missing fields
    4. If still fails, skip the field entirely
    
    Args:
        field_data: Raw field dictionary from LLM
        field_index: Index in parent's field list (for logging)
        section_path: Path to parent section (for logging)
        
    Returns:
        Validated Field instance, or None if unrecoverable
    """
    field_path = f"{section_path}.fields[{field_index}]"
    
    # Step 1: Remove extra fields
    cleaned_data, removed_keys = _clean_dict_for_model(field_data, Field)
    if removed_keys:
        log(f"  [LENIENT] Removed extra fields from {field_path}: {removed_keys}")
    
    # Step 2: Fix invalid enum values
    cleaned_data = _fix_enum_values(cleaned_data, field_path)
    
    # Step 3: Apply defaults for missing fields
    defaults = _get_model_defaults(Field)
    for key, default_value in defaults.items():
        if key not in cleaned_data:
            cleaned_data[key] = default_value
    
    # Handle required fields that have no default
    if "id" not in cleaned_data or cleaned_data["id"] is None:
        cleaned_data["id"] = field_index + 1
    if "name" not in cleaned_data or cleaned_data["name"] is None:
        cleaned_data["name"] = f"Field {field_index + 1}"
    if "rating_type" not in cleaned_data:
        cleaned_data["rating_type"] = RatingType.RADIO.value
    
    # Step 4: Try validation
    try:
        return Field.model_validate(cleaned_data)
    except ValidationError as e:
        log(f"  [LENIENT] Skipping invalid field at {field_path}: {e}")
        return None


def validate_section_lenient(
    section_data: dict[str, Any], 
    section_path: str = "root"
) -> Section | None:
    """
    Recursively validate a section and its children with lenient error handling.
    
    Strategy:
    1. Remove extra fields from section
    2. Fix invalid enum values (display_type)
    3. Recursively validate child sections (skip invalid ones)
    4. Validate fields individually (skip invalid ones)
    5. If section itself is invalid, return None
    
    Args:
        section_data: Raw section dictionary from LLM
        section_path: Path for logging (e.g., "root.sections[0].sections[1]")
        
    Returns:
        Validated Section instance (possibly with some children skipped), or None
    """
    # Step 1: Remove extra fields at section level
    cleaned_data, removed_keys = _clean_dict_for_model(section_data, Section)
    if removed_keys:
        log(f"  [LENIENT] Removed extra fields from {section_path}: {removed_keys}")
    
    # Step 2: Fix invalid enum values
    cleaned_data = _fix_enum_values(cleaned_data, section_path)
    
    # Step 3: Recursively validate child sections
    valid_sections = []
    raw_sections = section_data.get("sections", [])
    for i, child_section in enumerate(raw_sections):
        child_path = f"{section_path}.sections[{i}]"
        validated_child = validate_section_lenient(child_section, child_path)
        if validated_child is not None:
            valid_sections.append(validated_child)
    
    # Step 4: Validate fields individually
    valid_fields = []
    raw_fields = section_data.get("fields", [])
    for i, field_data in enumerate(raw_fields):
        validated_field = validate_field_lenient(field_data, i, section_path)
        if validated_field is not None:
            valid_fields.append(validated_field)
    
    # Replace with validated children
    cleaned_data["sections"] = valid_sections
    cleaned_data["fields"] = valid_fields
    
    # Apply defaults for missing required fields
    if "name" not in cleaned_data:
        cleaned_data["name"] = "Unknown Section"
    
    defaults = _get_model_defaults(Section)
    for key, default_value in defaults.items():
        if key not in cleaned_data:
            cleaned_data[key] = default_value
    
    # Step 5: Try to validate the section
    try:
        return Section.model_validate(cleaned_data)
    except ValidationError as e:
        log(f"  [LENIENT] Skipping invalid section at {section_path}: {e}")
        return None


def validate_template_lenient(template_data: dict[str, Any]) -> InspectionTemplate:
    """
    Validate an entire template with lenient tree-traversal approach.
    
    This method walks the template tree and validates each node individually,
    skipping or fixing malformed nodes rather than failing the entire validation.
    
    Args:
        template_data: Raw template dictionary from LLM
        
    Returns:
        Validated InspectionTemplate (possibly with some sections/fields skipped)
        
    Raises:
        ValidationError: If the template itself (not children) has critical errors
    """
    log("[LENIENT] Starting lenient tree-traversal validation...")
    
    # Remove extra fields at template level
    cleaned_template, removed_keys = _clean_dict_for_model(template_data, InspectionTemplate)
    if removed_keys:
        log(f"  [LENIENT] Removed extra fields from template: {removed_keys}")
    
    # Process versions
    valid_versions = []
    raw_versions = template_data.get("versions", [])
    
    for v_idx, version_data in enumerate(raw_versions):
        # Clean version data
        version_cleaned, v_removed = _clean_dict_for_model(version_data, TemplateVersion)
        if v_removed:
            log(f"  [LENIENT] Removed extra fields from versions[{v_idx}]: {v_removed}")
        
        # Validate the structure (root section) within each version
        raw_structure = version_data.get("structure")
        if raw_structure:
            validated_structure = validate_section_lenient(
                raw_structure, 
                f"versions[{v_idx}].structure"
            )
            if validated_structure is not None:
                # Build the version with validated structure
                version_final = {
                    "version_id": version_cleaned.get("version_id", v_idx + 1),
                    "structure": validated_structure,
                }
                try:
                    valid_versions.append(TemplateVersion.model_validate(version_final))
                except ValidationError as e:
                    log(f"  [LENIENT] Skipping invalid version {v_idx}: {e}")
    
    # Update cleaned template with validated versions
    cleaned_template["versions"] = valid_versions
    
    # Apply defaults for missing required fields
    if "id" not in cleaned_template:
        cleaned_template["id"] = 1
    if "name" not in cleaned_template:
        cleaned_template["name"] = "Extracted Inspection Template"
    
    defaults = _get_model_defaults(InspectionTemplate)
    for key, default_value in defaults.items():
        if key not in cleaned_template:
            cleaned_template[key] = default_value
    
    # Count what we processed
    total_sections = sum(
        _count_sections(v.structure) for v in valid_versions
    )
    total_fields = sum(
        _count_fields(v.structure) for v in valid_versions
    )
    log(f"[LENIENT] Validation complete: {len(valid_versions)} versions, {total_sections} sections, {total_fields} fields")
    
    return InspectionTemplate.model_validate(cleaned_template)


def _count_sections(section: Section) -> int:
    """Count total sections in a section tree."""
    return 1 + sum(_count_sections(s) for s in section.sections)


def _count_fields(section: Section) -> int:
    """Count total fields in a section tree."""
    return len(section.fields) + sum(_count_fields(s) for s in section.sections)

