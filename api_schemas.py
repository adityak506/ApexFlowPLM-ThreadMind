"""Pydantic schemas for Mock PLM FastAPI REST API.

Defines normalized request and response models for Part Catalog, BOM Exploration,
Issues Diagnostics, Change Management, Impact Analysis, and Error Handling.
"""

import math
from typing import Any
from pydantic import BaseModel, Field
from erp_interface import ERPInventorySummary, ERPPurchaseOrder
from iiot_interface import IIoTSensorEvent
from plm_interface import (
    BomComparisonItem,
    BomComparisonResult,
    BomLink,
    ChangeCategory,
    ChangeImpactAnalysis,
    ChangePriority,
    ChangeRequest,
    DuplicateGroup,
    ObsoleteUsageItem,
    Part,
)
from qms_interface import QMSDefectReport


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseModel):
    """Standardized error envelope returned for all API exceptions."""
    error: str = Field(..., description="High-level error classification or exception type")
    message: str = Field(..., description="Human-readable description of what went wrong")
    detail: Any = Field(None, description="Optional structured debug or validation details")


# =============================================================================
# Parts & Catalog Schemas
# =============================================================================

class PaginatedPartsResponse(BaseModel):
    """Paginated part catalog search response."""
    items: list[Part]
    total: int
    page: int
    page_size: int
    total_pages: int


class WhereUsedItem(BaseModel):
    """Consuming parent assembly record from where-used traversal."""
    parent_part_number: str
    parent_name: str
    parent_version: str
    parent_lifecycle_state: str
    quantity: float
    unit: str
    find_number: int | None = None
    level: int = 1


# =============================================================================
# BOM Comparison Schemas
# =============================================================================

class BomCompareRequest(BaseModel):
    """Payload for comparing two assembly BOMs or EBOM vs MBOM."""
    assembly_a: str = Field(..., min_length=1, max_length=100, description="First assembly identifier, e.g. PMP-0001 or PMP-0001:A.1")
    assembly_b: str = Field(..., min_length=1, max_length=100, description="Second assembly identifier, e.g. PMP-0002 or PMP-0001:MBOM")


# =============================================================================
# Planted Issues & Diagnostics Schemas
# =============================================================================

class IssuesSummaryResponse(BaseModel):
    """Aggregate summary count of all planted data quality issues."""
    duplicates: int = Field(..., description="Count of duplicate part groups")
    obsolete_in_released: int = Field(..., description="Count of obsolete parts consumed in released assemblies")
    unassigned_buy: int = Field(..., description="Count of BUY parts with no AML approved suppliers")
    ebom_mbom_mismatches: int = Field(..., description="Count of discrepancies between EBOM and MBOM")
    rohs_risks: int = Field(..., description="Count of parts violating RoHS compliance")
    total_issues: int = Field(..., description="Total combined issue count")


class IssueDetailResponse(BaseModel):
    """Paginated list of specific data health issues."""
    issue_type: str
    total: int
    page: int
    page_size: int
    total_pages: int
    items: list[Any]


# =============================================================================
# Change Impact Analysis Schemas
# =============================================================================

class ImpactRequest(BaseModel):
    """Request payload for evaluating blast radius of altering or obsoleting a component."""
    part_number: str = Field(..., min_length=1, max_length=50, description="Target part number to analyze")


# =============================================================================
# Change Management Schemas (Draft vs Confirm Safety Gate)
# =============================================================================

class DraftChangeRequestInput(BaseModel):
    """Input payload for proposing a new change request.
    
    Always creates a draft preview first without modifying persistent state.
    """
    title: str = Field(..., min_length=1, max_length=255, description="Short descriptive title of the change proposal")
    affected_parts: list[str] = Field(..., min_length=1, description="List of part numbers affected by this change")
    reason: str = Field(..., min_length=1, max_length=5000, description="Engineering justification or failure root cause")
    category: str = Field("DESIGN_IMPROVEMENT", description="Change classification category")
    priority: str = Field("MEDIUM", description="Change urgency ranking")


class DraftChangeResponse(BaseModel):
    """Response returned upon drafting an uncommitted change request."""
    draft_id: str
    title: str
    reason: str
    affected_parts: list[str]
    category: str
    priority: str
    status: str = "DRAFT"
    is_persisted: bool = False
    message: str


class ConfirmChangeResponse(BaseModel):
    """Response returned upon confirming and committing a change request."""
    cr_number: str
    title: str
    reason: str
    affected_parts: list[str]
    category: str
    priority: str
    status: str = "OPEN"
    is_persisted: bool = True
    message: str


class RejectChangeResponse(BaseModel):
    """Response returned upon rejecting and discarding an uncommitted change request."""
    draft_id: str
    status: str = "REJECTED"
    is_persisted: bool = False
    message: str


class PaginatedChangesResponse(BaseModel):
    """Paginated list of committed change requests."""
    items: list[ChangeRequest]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Digital Thread Schemas
# =============================================================================

class DigitalThreadTimelineEvent(BaseModel):
    """Chronological event in the cross-domain digital thread."""
    id: str = Field(..., description="Unique event or record identifier")
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    domain: str = Field(..., description="Domain origin: 'IIOT', 'QMS', 'PLM', 'ERP', or 'CHANGE'")
    event_type: str = Field(..., description="Classification category of the event")
    title: str = Field(..., description="Human-readable event headline")
    description: str = Field(..., description="Detailed context, diagnostics, or notes")
    severity: str = Field("INFO", description="Event severity: 'CRITICAL', 'WARNING', or 'INFO'")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Domain specific telemetry or payload")


class DigitalThreadResponse(BaseModel):
    """Consolidated digital thread payload for an engineering component."""
    part_number: str
    part_name: str
    part: Part | None = None
    stock_summary: ERPInventorySummary | None = None
    open_pos: list[ERPPurchaseOrder] = Field(default_factory=list)
    defects: list[QMSDefectReport] = Field(default_factory=list)
    telemetry_events: list[IIoTSensorEvent] = Field(default_factory=list)
    impact: ChangeImpactAnalysis | None = None
    timeline: list[DigitalThreadTimelineEvent] = Field(default_factory=list)


# =============================================================================
# AI Assistant Schemas
# =============================================================================

class ChatMessage(BaseModel):
    """Individual message in conversation history."""
    role: str = Field(..., description="Message author role: 'user', 'assistant', or 'system'")
    content: str = Field(..., description="Message text content")


class ToolCallRecord(BaseModel):
    """Metadata trace for a tool executed during AI reasoning."""
    tool: str = Field(..., description="Name of the PLM MCP tool invoked")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments passed to the tool")
    status: str = Field("SUCCESS", description="Execution status: 'SUCCESS' or 'ERROR'")
    result_count: int | None = Field(None, description="Number of items returned by the tool")
    summary: str | None = Field(None, description="Short summary of tool results")


class ChatRequest(BaseModel):
    """Request payload sent to POST /chat."""
    message: str = Field(..., min_length=1, max_length=5000, description="User prompt or engineering query")
    history: list[ChatMessage] = Field(default_factory=list, description="Prior conversation context")


class ChatResponse(BaseModel):
    """Consolidated response payload for non-streaming callers."""
    response: str
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    draft_created: dict[str, Any] | None = None
