"""Bill of Materials (BOM) models and product structure schemas."""

from pydantic import BaseModel, Field


class BOMLink(BaseModel):
    """Windchill WTPartUsageLink equivalent linking parent PartVersion to child PartMaster."""

    id: str
    parent_version_id: str
    child_master_id: str
    child_part_number: str
    child_name: str
    quantity: float = 1.0
    unit: str = "ea"
    find_number: int | None = None
    ref_designators: str | None = None
    notes: str = ""


class BOMNode(BaseModel):
    """Hierarchical node for multi-level indented BOM explosion."""

    part_number: str
    name: str
    version_label: str
    lifecycle_state: str
    quantity: float = 1.0
    unit: str = "ea"
    find_number: int | None = None
    ref_designators: str | None = None
    level: int = 0
    children: list["BOMNode"] = Field(default_factory=list)


class WhereUsedItem(BaseModel):
    """Record representing where a part is consumed as a component."""

    parent_part_number: str
    parent_name: str
    parent_version_label: str
    parent_lifecycle_state: str
    quantity: float
    unit: str
    find_number: int | None = None

