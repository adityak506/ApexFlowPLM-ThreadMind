"""Change management models for Engineering Change Requests (ECR) and Notices (ECN)."""

from datetime import datetime
from pydantic import BaseModel, Field
from plm_mcp.models.enums import (
    ChangeCategory,
    ChangeNoticeState,
    ChangePriority,
    ChangeRequestState,
    ItemDisposition,
    LifecycleState,
)


class ChangeAffectedItem(BaseModel):
    """An item (part or document) affected by a Change Notice with disposition."""

    id: str
    change_notice_id: str
    item_type: str  # "PART" or "DOCUMENT"
    item_number: str
    version_label: str
    disposition: ItemDisposition = ItemDisposition.USE_AS_IS


class ChangeResultingItem(BaseModel):
    """A new or revised item resulting from an implemented Change Notice."""

    id: str
    change_notice_id: str
    item_type: str  # "PART" or "DOCUMENT"
    item_number: str
    target_version_label: str
    target_state: LifecycleState = LifecycleState.RELEASED


class ChangeRequest(BaseModel):
    """Windchill WTChangeRequest2 equivalent (ECR)."""

    id: str
    cr_number: str
    title: str
    description: str
    category: ChangeCategory = ChangeCategory.DESIGN_IMPROVEMENT
    priority: ChangePriority = ChangePriority.MEDIUM
    state: ChangeRequestState = ChangeRequestState.OPEN
    affected_part_numbers: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChangeNotice(BaseModel):
    """Windchill WTChangeOrder2 equivalent (ECN)."""

    id: str
    cn_number: str
    change_request_id: str | None = None
    cr_number: str | None = None
    title: str
    description: str
    state: ChangeNoticeState = ChangeNoticeState.OPEN
    affected_items: list[ChangeAffectedItem] = Field(default_factory=list)
    resulting_items: list[ChangeResultingItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

