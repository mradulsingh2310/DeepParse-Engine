"""
Pydantic Schema Models for Inspection Templates
"""

from __future__ import annotations
from pydantic import BaseModel, ConfigDict


class Field(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    description: str | None = None
    mandatory: bool = False
    rating_type: str = "RATING_TYPE_UNSPECIFIED"
    options: list[str] = []
    notes_enabled: bool = False
    notes_required_for_all_options: bool = False
    notes_required_for_selected_options: list[str] = []
    attachments_enabled: bool = False
    attachments_required_for_all_options: bool = False
    attachments_required_for_selected_options: list[str] = []
    can_create_work_order: bool = False
    work_order_category: str = "MAINTENANCE_CATEGORY_UNSPECIFIED"
    work_order_sub_category: str = "WORK_ORDER_SUB_CATEGORY_UNSPECIFIED"
    value: str | list[str] | None = None


class Section(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    display_type: str = "SECTION_DISPLAY_TYPE_UNSPECIFIED"
    sections: list[Section] = []
    fields: list[Field] = []


class TemplateVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: int
    structure: Section


class InspectionTemplate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    name: str
    description: str | None = None
    property_ids: list[int] = []
    versions: list[TemplateVersion] = []
    created_at: str | None = None
    updated_at: str | None = None


Section.model_rebuild()
