"""Document data models and part-document association schemas."""

from datetime import datetime
from pydantic import BaseModel, Field
from plm_mcp.models.enums import DocType, LifecycleState, PartDocLinkType


class DocumentMaster(BaseModel):
    """Document master identity in Windchill semantics (WTDocumentMaster)."""

    id: str
    doc_number: str
    name: str
    doc_type: DocType = DocType.SPECIFICATION
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DocumentVersion(BaseModel):
    """Specific revision and iteration instance of a document (e.g. A.1)."""

    id: str
    master_id: str
    doc_number: str
    name: str
    doc_type: DocType
    revision: str = "A"
    iteration: int = 1
    version_label: str = "A.1"
    lifecycle_state: LifecycleState = LifecycleState.IN_WORK
    file_name: str | None = None
    file_size_bytes: int | None = None
    mime_type: str | None = None
    file_uri: str | None = None
    created_by: str = "wcadmin"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class PartDocLink(BaseModel):
    """Windchill WTPartDescribeLink / WTPartReferenceLink equivalent."""

    id: str
    part_version_id: str
    doc_version_id: str
    part_number: str
    doc_number: str
    doc_name: str
    doc_version_label: str
    link_type: PartDocLinkType = PartDocLinkType.DESCRIBES

