"""FastAPI REST API wrapping PLMBackend.

Provides RESTful endpoints for:
- Part catalog search and retrieval (GET /parts, GET /parts/{number})
- Multi-level BOM exploration and where-used analysis (GET /parts/{number}/bom, GET /parts/{number}/where-used)
- BOM comparison (POST /bom/compare)
- Data health diagnostics and planted issues (GET /issues/summary, GET /issues/{type})
- Change impact blast-radius analysis (POST /impact)
- Change management with two-step safety gate (GET /changes, POST /changes/draft, POST /changes/{id}/confirm)

Constraints:
- Strictly calls PLMBackend interface only; never interacts directly with SQLite or Windchill.
- Dynamic backend selection driven by PLM_BACKEND ('mock' or 'windchill').
- Write endpoints default to non-persisting drafts and require an explicit confirmation step to commit.
- Standardized error format across all endpoints.
- CORS configured for http://localhost:5173.
"""

import sys
from pathlib import Path

# Ensure application root directory and src/ are in sys.path
_APP_ROOT = str(Path(__file__).resolve().parent)
if _APP_ROOT not in sys.path:
    sys.path.insert(0, _APP_ROOT)
_SRC_DIR = str(Path(__file__).resolve().parent / "src")
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import datetime
import math
import os
import uuid
from typing import Any
from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api_schemas import (
    BomCompareRequest,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ConfirmChangeResponse,
    DigitalThreadResponse,
    DigitalThreadTimelineEvent,
    DraftChangeRequestInput,
    DraftChangeResponse,
    ErrorResponse,
    ImpactRequest,
    IssueDetailResponse,
    IssuesSummaryResponse,
    PaginatedChangesResponse,
    PaginatedPartsResponse,
    RejectChangeResponse,
    WhereUsedItem,
)
from chat_service import stream_chat_events
from erp_interface import ERPBackend
from iiot_interface import IIoTBackend
from mock_backend import MockBackend
from mock_erp_backend import MockERPBackend
from mock_iiot_backend import MockIIoTBackend
from mock_qms_backend import MockQMSBackend
from plm_interface import (
    BomComparisonResult,
    BomLink,
    ChangeImpactAnalysis,
    ChangeRequest,
    Part,
    PLMBackend,
)
from qms_interface import QMSBackend
from windchill_backend import WindchillBackend

# OpenTelemetry Observability & Middleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from telemetry import (
    RequestIDMiddleware,
    init_telemetry,
    record_agent_quality_issue,
    record_ecr_transition,
    record_impact_analysis,
    record_issue_detected,
)


# =============================================================================
# Backend Factory & In-Memory Draft Store
# =============================================================================

def get_backend() -> PLMBackend:
    """Retrieve active PLM backend driven by PLM_BACKEND env var.
    
    Defaults to MockBackend (SQLite) unless PLM_BACKEND is set to 'windchill'.
    """
    backend_type = os.getenv("PLM_BACKEND", "mock").strip().lower()
    if backend_type == "windchill":
        return WindchillBackend()
    db_path = os.getenv("PLM_SQLITE_PATH", "plm_mock.db")
    return MockBackend(db_path=db_path)


def get_erp_backend() -> ERPBackend:
    """Retrieve active ERP backend instance."""
    db_path = os.getenv("PLM_SQLITE_PATH", "plm_mock.db")
    return MockERPBackend(db_path=db_path)


def get_qms_backend() -> QMSBackend:
    """Retrieve active QMS backend instance."""
    db_path = os.getenv("PLM_SQLITE_PATH", "plm_mock.db")
    return MockQMSBackend(db_path=db_path)


def get_iiot_backend() -> IIoTBackend:
    """Retrieve active IIoT backend instance."""
    db_path = os.getenv("PLM_SQLITE_PATH", "plm_mock.db")
    return MockIIoTBackend(db_path=db_path)


# In-memory store for pending uncommitted drafts (draft_id -> draft_data)
# Write actions strictly default to draft and require an explicit confirm step
PENDING_DRAFTS: dict[str, dict[str, Any]] = {}


# =============================================================================
# FastAPI Application & CORS Configuration
# =============================================================================

app = FastAPI(
    title="Mock PLM REST API",
    description="PTC Windchill-style PLM REST API wrapping PLMBackend with strict two-step change safety gates.",
    version="1.0.0",
)

# Request ID correlation middleware (X-Request-ID)
app.add_middleware(RequestIDMiddleware)

# Configure CORS origins from environment or default to local dev + Vercel wildcard regex
cors_env = os.getenv("CORS_ORIGINS", "").strip()
if cors_env:
    allowed_origins = [o.strip() for o in cors_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

cors_allow_all = os.getenv("CORS_ALLOW_ALL", "false").strip().lower() in ("true", "1", "yes")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if cors_allow_all else allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app" if not cors_allow_all else None,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry FastAPI Auto-Instrumentation
try:
    FastAPIInstrumentor.instrument_app(app)
except Exception:
    pass


# =============================================================================
# Consistent Error Format Handlers
# =============================================================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Ensure HTTP exceptions follow the standard ErrorResponse model."""
    error_type = "HTTPException"
    if exc.status_code == 404:
        error_type = "NotFound"
    elif exc.status_code == 400:
        error_type = "BadRequest"
    elif exc.status_code == 403:
        error_type = "Forbidden"

    error_payload = ErrorResponse(
        error=error_type,
        message=str(exc.detail),
        detail=None,
    )
    return JSONResponse(status_code=exc.status_code, content=error_payload.model_dump())


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Ensure Pydantic validation errors follow the standard ErrorResponse model."""
    error_payload = ErrorResponse(
        error="ValidationError",
        message="Invalid request parameters or payload.",
        detail=exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=error_payload.model_dump(),
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    """Ensure ValueErrors raised by validators return 400 with standard ErrorResponse."""
    error_payload = ErrorResponse(
        error="ValueError",
        message=str(exc),
        detail=None,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error_payload.model_dump(),
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for unhandled server exceptions returning 500 with standard ErrorResponse."""
    error_payload = ErrorResponse(
        error="InternalServerError",
        message="An unexpected server error occurred.",
        detail=str(exc),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=error_payload.model_dump(),
    )


# =============================================================================
# Health & Status Endpoint
# =============================================================================

@app.get(
    "/health",
    summary="Health check probe for system status and active backend",
    tags=["System"],
)
def get_health() -> dict[str, Any]:
    """Lightweight health check endpoint returning backend type, status, and uptime timestamp."""
    backend_type = os.getenv("PLM_BACKEND", "mock").strip().lower()
    return {
        "status": "healthy",
        "backend": backend_type,
        "version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }


# =============================================================================
# Part Catalog Endpoints
# =============================================================================

@app.get(
    "/parts",
    response_model=PaginatedPartsResponse,
    summary="Search parts catalog with pagination",
    tags=["Parts"],
)
def list_parts(
    query: str = Query("", description="Search substring matching part number, name, or description"),
    lifecycle_state: str | None = Query(None, description="Optional lifecycle state filter"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    backend: PLMBackend = Depends(get_backend),
) -> PaginatedPartsResponse:
    """Retrieve a paginated list of components resolving to their latest version."""
    skip = (page - 1) * page_size
    items = backend.search_parts(
        query=query,
        lifecycle_state=lifecycle_state,
        limit=page_size,
        skip=skip,
    )
    total = backend.get_parts_count(query=query, lifecycle_state=lifecycle_state)
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedPartsResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@app.get(
    "/parts/{number}",
    response_model=Part,
    summary="Get part details by part number",
    tags=["Parts"],
)
def get_part_by_number(
    number: str,
    version: str | None = Query(None, description="Optional revision or iteration, e.g. 'A.1'"),
    backend: PLMBackend = Depends(get_backend),
) -> Part:
    """Retrieve full part record for a specific or latest revision."""
    part = backend.get_part(part_number=number, version=version)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part '{number}' not found.",
        )
    return part


# =============================================================================
# Bill of Materials (BOM) & Where-Used Endpoints
# =============================================================================

@app.get(
    "/parts/{number}/bom",
    response_model=list[BomLink],
    summary="Retrieve single or multi-level indented BOM",
    tags=["BOM"],
)
def get_part_bom(
    number: str,
    levels: int = Query(1, ge=1, le=10, description="Explosion depth (1 for single-level, >1 for multi-level)"),
    backend: PLMBackend = Depends(get_backend),
) -> list[BomLink]:
    """Retrieve single-level or multi-level indented BOM links for an assembly."""
    part = backend.get_part(part_number=number)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Assembly '{number}' not found.",
        )
    return backend.get_bom(part_number=number, levels=levels)


@app.get(
    "/parts/{number}/where-used",
    response_model=list[WhereUsedItem],
    summary="Find consuming parent assemblies (where-used)",
    tags=["BOM"],
)
def get_part_where_used(
    number: str,
    recursive: bool = Query(False, description="Whether to traverse recursively up to root assemblies"),
    backend: PLMBackend = Depends(get_backend),
) -> list[WhereUsedItem]:
    """Trace all parent assemblies that consume this part in their BOM."""
    part = backend.get_part(part_number=number)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part '{number}' not found.",
        )
    records = backend.where_used(part_number=number, recursive=recursive)
    return [
        WhereUsedItem(
            parent_part_number=r["parent_part_number"],
            parent_name=r["parent_name"],
            parent_version=r["parent_version"],
            parent_lifecycle_state=r["parent_lifecycle_state"],
            quantity=r["quantity"],
            unit=r.get("unit", "ea"),
            find_number=r.get("find_number"),
            level=r.get("level", 1),
        )
        for r in records
    ]


@app.post(
    "/bom/compare",
    response_model=BomComparisonResult,
    summary="Compare two BOM structures or EBOM vs MBOM",
    tags=["BOM"],
)
def compare_boms_endpoint(
    req: BomCompareRequest,
    backend: PLMBackend = Depends(get_backend),
) -> BomComparisonResult:
    """Compare two assembly BOM structures or configurations, returning added, removed, and modified parts."""
    return backend.compare_boms(a=req.assembly_a, b=req.assembly_b)


# =============================================================================
# Planted Issues & Diagnostics Endpoints
# =============================================================================

@app.get(
    "/issues/summary",
    response_model=IssuesSummaryResponse,
    summary="Get summary count of all planted data quality issues",
    tags=["Diagnostics"],
)
def get_issues_summary(
    backend: PLMBackend = Depends(get_backend),
) -> IssuesSummaryResponse:
    """Return aggregated count of all 5 planted data health issues across the catalog."""
    duplicates = backend.find_duplicates()
    obsolete = backend.find_obsolete_in_released()
    unassigned = backend.find_unassigned_buy_parts()
    mismatches = backend.find_ebom_mbom_mismatches()
    rohs = backend.find_rohs_risks()

    dup_count = len(duplicates)
    obs_count = len(obsolete)
    unassigned_count = len(unassigned)
    mismatch_count = len(mismatches)
    rohs_count = len(rohs)
    total = dup_count + obs_count + unassigned_count + mismatch_count + rohs_count

    # Record custom business metrics
    record_issue_detected("duplicates", dup_count)
    record_issue_detected("obsolete_in_released", obs_count)
    record_issue_detected("unassigned_buy", unassigned_count)
    record_issue_detected("ebom_mbom_mismatches", mismatch_count)
    record_issue_detected("rohs_risks", rohs_count)

    return IssuesSummaryResponse(
        duplicates=dup_count,
        obsolete_in_released=obs_count,
        unassigned_buy=unassigned_count,
        ebom_mbom_mismatches=mismatch_count,
        rohs_risks=rohs_count,
        total_issues=total,
    )


@app.get(
    "/issues/{type}",
    response_model=IssueDetailResponse,
    summary="Get paginated list of items for a specific issue type",
    tags=["Diagnostics"],
)
def get_issues_by_type(
    type: str,
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    backend: PLMBackend = Depends(get_backend),
) -> IssueDetailResponse:
    """Return paginated items for a specific data health issue type."""
    normalized_type = type.lower().replace("-", "_")

    if normalized_type == "duplicates":
        raw_items: list[Any] = backend.find_duplicates()
    elif normalized_type == "obsolete_in_released":
        raw_items = backend.find_obsolete_in_released()
    elif normalized_type in ("unassigned_buy", "no_supplier"):
        raw_items = backend.find_unassigned_buy_parts()
    elif normalized_type == "ebom_mbom_mismatches":
        raw_items = backend.find_ebom_mbom_mismatches()
    elif normalized_type == "rohs_risks":
        raw_items = backend.find_rohs_risks()
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported issue type '{type}'. Valid types are: "
                "duplicates, obsolete_in_released, unassigned_buy, "
                "ebom_mbom_mismatches, rohs_risks."
            ),
        )

    total = len(raw_items)
    record_issue_detected(normalized_type, total)
    skip = (page - 1) * page_size
    paginated_items = raw_items[skip : skip + page_size]
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return IssueDetailResponse(
        issue_type=normalized_type,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=paginated_items,
    )


# =============================================================================
# Change Impact Analysis Endpoint
# =============================================================================

@app.post(
    "/impact",
    response_model=ChangeImpactAnalysis,
    summary="Analyze change blast radius for a part",
    tags=["Change Management"],
)
def analyze_impact_endpoint(
    req: ImpactRequest,
    backend: PLMBackend = Depends(get_backend),
) -> ChangeImpactAnalysis:
    """Evaluate cross-functional blast radius of altering or obsoleting a component."""
    part = backend.get_part(part_number=req.part_number)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part '{req.part_number}' not found.",
        )
    result = backend.analyze_change_impact(part_number=req.part_number)
    record_impact_analysis(1)
    return result


# =============================================================================
# Change Requests (Two-Step Draft vs Confirm Safety Gate)
# =============================================================================

@app.get(
    "/changes",
    response_model=PaginatedChangesResponse,
    summary="List committed change requests with pagination",
    tags=["Change Management"],
)
def list_change_requests(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(20, ge=1, le=500, description="Items per page"),
    status: str | None = Query(None, description="Optional state filter ('OPEN', 'APPROVED', etc.)"),
    backend: PLMBackend = Depends(get_backend),
) -> PaginatedChangesResponse:
    """Retrieve paginated list of committed change requests."""
    skip = (page - 1) * page_size
    items = backend.get_change_requests(status=status, limit=page_size, skip=skip)
    total = backend.get_change_requests_count(status=status)
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return PaginatedChangesResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


@app.post(
    "/changes/draft",
    response_model=DraftChangeResponse,
    status_code=status.HTTP_200_OK,
    summary="Draft a new change request (dry-run, not persisted)",
    tags=["Change Management"],
)
def draft_change_endpoint(
    req: DraftChangeRequestInput,
    backend: PLMBackend = Depends(get_backend),
) -> DraftChangeResponse:
    """Create a draft change request preview.
    
    SAFETY GATE:
    This endpoint is non-mutating and does NOT commit to the database (is_persisted=False).
    To commit this change request to the PLM database, an explicit call to
    POST /changes/{id}/confirm must be made with the returned draft_id.
    """
    # Pre-validate that all affected parts exist in the catalog
    missing_parts: list[str] = []
    for p_no in req.affected_parts:
        part = backend.get_part(p_no)
        if not part:
            missing_parts.append(p_no)

    if missing_parts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"The following affected parts do not exist in the catalog: {missing_parts}",
        )

    # Generate draft preview identifier
    draft_id = f"DRAFT-{uuid.uuid4().hex[:8].upper()}"
    draft_record = {
        "draft_id": draft_id,
        "title": req.title.strip(),
        "reason": req.reason.strip(),
        "affected_parts": req.affected_parts,
        "category": req.category,
        "priority": req.priority,
    }
    PENDING_DRAFTS[draft_id] = draft_record
    record_ecr_transition("draft", 1)

    return DraftChangeResponse(
        draft_id=draft_id,
        title=draft_record["title"],
        reason=draft_record["reason"],
        affected_parts=draft_record["affected_parts"],
        category=draft_record["category"],
        priority=draft_record["priority"],
        status="DRAFT",
        is_persisted=False,
        message=(
            "DRAFT PREVIEW: Change request validated successfully, but NOT committed to the database. "
            f"Call POST /changes/{draft_id}/confirm to persist this change request."
        ),
    )


@app.post(
    "/changes/{id}/confirm",
    response_model=ConfirmChangeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Confirm and commit a draft change request to the database",
    tags=["Change Management"],
)
def confirm_change_endpoint(
    id: str,
    backend: PLMBackend = Depends(get_backend),
) -> ConfirmChangeResponse:
    """Explicitly confirm and persist a pending draft change request to the PLM database.
    
    Requires the draft_id generated by POST /changes/draft.
    """
    clean_id = id.strip()
    draft = PENDING_DRAFTS.pop(clean_id, None)

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft change request '{clean_id}' not found or already confirmed.",
        )

    # Commit mutation via PLMBackend interface
    cr: ChangeRequest = backend.draft_change_request(
        title=draft["title"],
        affected_parts=draft["affected_parts"],
        reason=draft["reason"],
    )
    record_ecr_transition("confirmed", 1)

    return ConfirmChangeResponse(
        cr_number=cr.cr_number,
        title=cr.title,
        reason=cr.reason,
        affected_parts=cr.affected_parts,
        category=cr.category.value if hasattr(cr.category, "value") else str(cr.category),
        priority=cr.priority.value if hasattr(cr.priority, "value") else str(cr.priority),
        status=cr.status,
        is_persisted=True,
        message=f"Change Request '{cr.cr_number}' successfully created and committed to the PLM database.",
    )


@app.post(
    "/changes/{id}/reject",
    response_model=RejectChangeResponse,
    status_code=status.HTTP_200_OK,
    summary="Reject and discard an unpersisted draft change request",
    tags=["Change Management"],
)
def reject_change_endpoint(id: str) -> RejectChangeResponse:
    """Explicitly reject and discard a pending draft change request.
    
    Records agent quality degradation counter: threadmind_agent_quality_issues_total{reason=rejected_draft}.
    """
    clean_id = id.strip()
    draft = PENDING_DRAFTS.pop(clean_id, None)

    if not draft:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Draft change request '{clean_id}' not found or already processed.",
        )

    record_ecr_transition("rejected", 1)
    record_agent_quality_issue("rejected_draft", 1)

    return RejectChangeResponse(
        draft_id=clean_id,
        status="REJECTED",
        is_persisted=False,
        message=f"Draft change request '{clean_id}' has been rejected and discarded.",
    )


# =============================================================================
# Digital Thread Endpoints (IIoT + QMS + PLM + ERP Unified View)
# =============================================================================

@app.get(
    "/digital-thread/{number}",
    response_model=DigitalThreadResponse,
    summary="Get cross-domain digital thread timeline and status for a part",
    tags=["Digital Thread"],
)
def get_digital_thread(
    number: str,
    backend: PLMBackend = Depends(get_backend),
    erp: ERPBackend = Depends(get_erp_backend),
    qms: QMSBackend = Depends(get_qms_backend),
    iiot: IIoTBackend = Depends(get_iiot_backend),
) -> DigitalThreadResponse:
    """Retrieve unified digital thread correlating ERP, QMS, IIoT, and PLM records."""
    clean_number = number.strip().upper()
    part = backend.get_part(part_number=clean_number)
    if not part:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Part '{clean_number}' not found in PLM catalog.",
        )

    # 1. Cross-domain queries
    stock = erp.get_stock(clean_number)
    pos = erp.get_open_pos(clean_number)
    defects = qms.get_defects(clean_number)
    telemetry = iiot.get_failure_events(part_number=clean_number)

    impact = None
    try:
        impact = backend.analyze_change_impact(clean_number)
    except Exception:
        pass

    # 2. Build unified chronological timeline
    timeline: list[DigitalThreadTimelineEvent] = []

    # PLM Part Baseline event
    timeline.append(
        DigitalThreadTimelineEvent(
            id=f"PLM-{clean_number}-RELEASE",
            timestamp=part.created_at.isoformat(),
            domain="PLM",
            event_type="PART_RELEASE",
            title=f"Part {clean_number} Revision {part.version_label} Released",
            description=f"{part.name} released into production baseline with material '{part.material or 'Standard'}'.",
            severity="INFO",
            metadata={"revision": part.version_label, "lifecycle_state": part.lifecycle_state.value},
        )
    )

    # IIoT Telemetry Anomaly events
    for evt in telemetry:
        evt_sev = evt.severity.value if hasattr(evt.severity, "value") else str(evt.severity)
        evt_ts = evt.timestamp if isinstance(evt.timestamp, str) else evt.timestamp.isoformat()
        timeline.append(
            DigitalThreadTimelineEvent(
                id=evt.event_id,
                timestamp=evt_ts,
                domain="IIOT",
                event_type=evt.event_type,
                title=f"IIoT Sensor Anomaly on Asset {evt.serial_number}",
                description=f"{evt.sensor_type.value.capitalize()} sensor reading {evt.metric_value} {evt.unit} exceeded threshold {evt.threshold_value} {evt.unit}. {evt.details}",
                severity=evt_sev,
                metadata={
                    "serial_number": evt.serial_number,
                    "metric_value": evt.metric_value,
                    "threshold": evt.threshold_value,
                    "unit": evt.unit,
                },
            )
        )

    # QMS Defect Non-conformance events
    for d in defects:
        d_sev = d.severity.value if hasattr(d.severity, "value") else str(d.severity)
        d_ts = d.created_at if isinstance(d.created_at, str) else d.created_at.isoformat()
        d_status = d.status.value if hasattr(d.status, "value") else str(d.status)
        timeline.append(
            DigitalThreadTimelineEvent(
                id=d.defect_number,
                timestamp=d_ts,
                domain="QMS",
                event_type=d.failure_mode,
                title=f"QMS Non-Conformance: {d.title}",
                description=f"{d.description} Status: {d_status}. Containment action: {d.containment_action}.",
                severity=d_sev,
                metadata={
                    "defect_number": d.defect_number,
                    "failure_mode": d.failure_mode,
                    "status": d_status,
                },
            )
        )

    # PLM Change Impact event
    if impact and impact.all_affected_assemblies:
        timeline.append(
            DigitalThreadTimelineEvent(
                id=f"PLM-{clean_number}-IMPACT",
                timestamp=part.updated_at.isoformat(),
                domain="PLM",
                event_type="IMPACT_ASSESSMENT",
                title=f"PLM Blast-Radius Calculated: {impact.impact_level} Severity",
                description=f"Part alteration impacts {len(impact.all_affected_assemblies)} parent assemblies ({', '.join(impact.all_affected_assemblies[:3])}) and {len(impact.associated_documents)} linked CAD drawings.",
                severity="CRITICAL" if impact.impact_level in ("CRITICAL", "HIGH") else "WARNING",
                metadata={"impact_level": impact.impact_level, "assemblies_count": len(impact.all_affected_assemblies)},
            )
        )

    # ERP Purchase Orders
    for po in pos:
        timeline.append(
            DigitalThreadTimelineEvent(
                id=f"ERP-{po.po_number}-{po.line_number}",
                timestamp=po.order_date,
                domain="ERP",
                event_type="PURCHASE_ORDER",
                title=f"Procurement PO {po.po_number}: {po.quantity_ordered} units from {po.supplier_name}",
                description=f"Status: {po.status}. Expected delivery: {po.expected_delivery}. Unit price: ${po.unit_price:,.2f} {po.currency}.",
                severity="WARNING" if po.status in ("OPEN", "IN_TRANSIT") else "INFO",
                metadata={"po_number": po.po_number, "quantity": po.quantity_ordered, "supplier": po.supplier_name},
            )
        )

    # ERP Stock Inventory Exposure
    if stock and stock.total_on_hand > 0:
        latest_counted = stock.stock_locations[0].last_counted if stock.stock_locations else "2025-02-01T08:00:00"
        wh_count = len(stock.stock_locations)
        total_val = stock.total_valuation
        timeline.append(
            DigitalThreadTimelineEvent(
                id=f"ERP-{clean_number}-STOCK",
                timestamp=latest_counted,
                domain="ERP",
                event_type="INVENTORY_BALANCE",
                title=f"Warehouse Stock Exposure: {stock.total_on_hand} Units (${total_val:,.2f})",
                description=f"Inventory distributed across {wh_count} warehouse(s): {stock.total_available} available, {stock.total_reserved} reserved for production.",
                severity="WARNING",
                metadata={"total_on_hand": stock.total_on_hand, "total_value_usd": total_val},
            )
        )

    # Sort chronologically by timestamp
    timeline.sort(key=lambda x: x.timestamp)

    return DigitalThreadResponse(
        part_number=part.part_number,
        part_name=part.name,
        part=part,
        stock_summary=stock,
        open_pos=pos,
        defects=defects,
        telemetry_events=telemetry,
        impact=impact,
        timeline=timeline,
    )


# =============================================================================
# AI Assistant Chat Endpoint (MCP Tool Invocation & Streaming)
# =============================================================================

@app.post(
    "/chat",
    responses={200: {"model": ChatResponse}},
    summary="AI Assistant with PLM MCP tool calling and SSE streaming",
    tags=["AI Assistant"],
)
async def chat_endpoint(
    req: ChatRequest,
    backend: PLMBackend = Depends(get_backend),
):
    """Conversational assistant connected to PLM MCP tools with streaming output.
    
    Streams Server-Sent Events (SSE) containing:
    - tool_call: tool invocation metadata
    - tool_result: tool execution outcome
    - draft_created: unpersisted ECR draft (if generated)
    - content_delta: response text chunks
    - done: final completion payload
    """
    return StreamingResponse(
        stream_chat_events(
            message=req.message,
            history=req.history,
            backend=backend,
            pending_drafts=PENDING_DRAFTS,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

