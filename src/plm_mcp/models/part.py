"""Part data models and versioning schemas."""

from datetime import datetime
from pydantic import BaseModel, Field
from plm_mcp.models.enums import LifecycleState


class PartMaster(BaseModel):
    """Part Master identity object in Windchill semantics."""

    id: str
    part_number: str
    name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PartVersion(BaseModel):
    """Specific revision and iteration instance of a part (e.g. A.1)."""

    id: str
    master_id: str
    part_number: str
    name: str
    revision: str = "A"
    iteration: int = 1
    version_label: str = "A.1"
    lifecycle_state: LifecycleState = LifecycleState.IN_WORK
    description: str = ""
    created_by: str = "wcadmin"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def format_version(cls, revision: str, iteration: int) -> str:
        """Format revision and iteration into standard Windchill label."""
        return f"{revision}.{iteration}"


class PartSummary(BaseModel):
    """Summary overview of a part for search listings."""

    part_number: str
    name: str
    version_label: str
    lifecycle_state: LifecycleState
    description: str = ""
    updated_at: datetime


class PartDetail(BaseModel):
    """Full detail view of a part version including associations."""

    master: PartMaster
    version: PartVersion
    bom_components_count: int = 0
    documents_count: int = 0
    aml_entries_count: int = 0

