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
    UNSPECIFIED = "SECTION_DISPLAY_TYPE_UNSPECIFIED"  # Section/parent container
    FIELD_SET = "SECTION_DISPLAY_TYPE_FIELD_SET"  # Leaf node containing fields


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
    - UNSPECIFIED: Section/parent container, contains child sections or field sets
    - FIELD_SET: Leaf node containing fields (has fields, NO child sections)
    
    Sections can be nested: Root → Sections → Field Sets, or Root → Field Sets directly.
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


def validate_template_lenient(data: dict) -> dict:
    """
    Validate template data leniently, allowing extra fields.
    
    This is used for LLM outputs that may include additional metadata.
    Returns the validated data dict (not a Pydantic model).
    """
    # Remove any metadata fields before validation
    clean_data = {k: v for k, v in data.items() if not k.startswith("_")}
    
    try:
        # Try strict validation first
        template = InspectionTemplate.model_validate(clean_data)
        return template.model_dump()
    except Exception as e:
        log(f"Strict validation failed, returning raw data: {e}")
        return clean_data