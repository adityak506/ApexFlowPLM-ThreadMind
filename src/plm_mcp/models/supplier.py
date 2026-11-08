"""Supplier and Sourcing models for AML/AVL management."""

from datetime import datetime
from pydantic import BaseModel, Field
from plm_mcp.models.enums import ManufacturerStatus, SourcingStatus


class Manufacturer(BaseModel):
    """External manufacturer / vendor organization entity."""

    id: str
    name: str
    cage_code: str | None = None
    status: ManufacturerStatus = ManufacturerStatus.ACTIVE
    country: str = "USA"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class ManufacturerPart(BaseModel):
    """Windchill WTManufacturerPart equivalent."""

    id: str
    manufacturer_id: str
    manufacturer_name: str
    mfr_part_number: str
    description: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AMLLink(BaseModel):
    """Windchill AXLLink associating internal part to manufacturer part."""

    id: str
    part_master_id: str
    internal_part_number: str
    mfr_part_id: str
    mfr_name: str
    mfr_part_number: str
    sourcing_status: SourcingStatus = SourcingStatus.APPROVED
    preference_rank: int = 1

