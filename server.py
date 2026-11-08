"""FastMCP Server exposing PLM operations and audits.

Exposes tools:
- search_parts
- get_part
- get_bom
- where_used
- compare_boms
- find_duplicates
- find_obsolete_in_released
- analyze_change_impact
- draft_change_request (defaults to DRAFT, requires confirm=True to persist)

Backend is selected dynamically via PLM_BACKEND env var ('mock' or 'windchill').
All tool calls are recorded in structured format in audit.log.
"""

import json
import os
from datetime import datetime
from functools import wraps
from typing import Any, Callable

from mcp.server.fastmcp import FastMCP
from mock_backend import MockBackend
from plm_interface import (
    BomComparisonResult,
    BomLink,
    ChangeImpactAnalysis,
    ChangeRequest,
    DuplicateGroup,
    ObsoleteUsageItem,
    Part,
    PLMBackend,
)
from windchill_backend import WindchillBackend

# Cross-Domain Interfaces and Mock Adapters
from erp_interface import (
    ERPBackend,
    ERPInventorySummary,
    ERPPurchaseOrder,
)
from mock_erp_backend import MockERPBackend

from qms_interface import (
    QMSBackend,
    QMSDefectReport,
)
from mock_qms_backend import MockQMSBackend

from iiot_interface import (
    IIoTBackend,
    IIoTDevice,
    IIoTSensorEvent,
)
from mock_iiot_backend import MockIIoTBackend

# Security, Input Validation & Audit Sanitization
from validators import (
    redact_sensitive_args,
    sanitize_text,
    validate_bom_levels,
    validate_lifecycle_state,
    validate_pagination_limit,
    validate_part_number,
    validate_part_numbers,
)
from telemetry import (
    instrument_tool,
    telemetry,
    logger,
    record_ecr_transition,
    record_impact_analysis,
    record_issue_detected,
)

# Initialize FastMCP Server
mcp = FastMCP(
    name="plm-mcp-server",
    instructions=(
        "Industrial PLM & Digital Thread MCP Server providing Windchill-style product structure queries, "
        "multi-level BOM explosions, where-used traversal, change impact analysis, quality audits, "
        "ERP inventory & purchase orders, QMS defect reports, and IIoT sensor telemetry failure tracking. "
        "Mutation tools default to draft preview and require confirm=True to commit."
    ),
)

AUDIT_LOG_FILE = "audit.log"


# =============================================================================
# Structured Audit Logging
# =============================================================================

def log_audit_entry(
    tool_name: str,
    args: dict[str, Any],
    result: Any = None,
    error: Exception | None = None,
    duration_ms: float = 0.0,
) -> None:
    """Record a structured JSON audit entry to audit.log with OpenTelemetry trace context."""
    from opentelemetry import trace
    from opentelemetry.trace import format_trace_id, format_span_id

    current_span = trace.get_current_span()
    span_ctx = current_span.get_span_context() if current_span else None
    trace_id_str = format_trace_id(span_ctx.trace_id) if span_ctx and span_ctx.is_valid else ""
    span_id_str = format_span_id(span_ctx.span_id) if span_ctx and span_ctx.is_valid else ""
    backend_name = os.getenv("PLM_BACKEND", "mock").strip().lower()

    if error is not None:
        result_count = 0
        status = "ERROR"
    elif isinstance(result, (list, tuple)):
        result_count = len(result)
        status = "SUCCESS"
    elif hasattr(result, "differences"):
        result_count = len(result.differences)
        status = "SUCCESS"
    elif hasattr(result, "all_affected_assemblies"):
        result_count = len(result.all_affected_assemblies)
        status = "SUCCESS"
    elif isinstance(result, dict) and "differences" in result:
        result_count = len(result["differences"])
        status = "SUCCESS"
    elif result is not None:
        result_count = 1
        status = "SUCCESS"
    else:
        result_count = 0
        status = "SUCCESS"

    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tool": tool_name,
        "tool_name": tool_name,
        "args": redact_sensitive_args(args),
        "status": status,
        "result_count": result_count,
        "trace_id": trace_id_str,
        "span_id": span_id_str,
        "backend": backend_name,
        "duration_ms": round(duration_ms, 2),
        "error": str(error) if error else None,
    }

    try:
        with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as log_err:
        # Fallback to stderr if file logging fails
        import sys
        print(f"[AUDIT LOG ERROR] Failed writing to {AUDIT_LOG_FILE}: {log_err}", file=sys.stderr)


def audit_tool(name: str) -> Callable:
    """Decorator that wraps an MCP tool function to provide OpenTelemetry spans, metrics, and structured JSON logging."""
    return instrument_tool(name)


# =============================================================================
# Backend Factory
# =============================================================================

def get_backend() -> PLMBackend:
    """Retrieve active backend instance based on PLM_BACKEND env var."""
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


# =============================================================================
# Tool Registrations
# =============================================================================

@mcp.tool()
@audit_tool("get_part")
def get_part(part_number: str, version: str | None = None) -> Part | dict[str, str]:
    """Retrieve details for a part by number and optional revision.iteration.

    Returns the latest iteration of the latest revision unless a specific version
    (e.g. 'A.1' or revision 'A') is provided.

    Args:
        part_number: Unique part identification number (e.g. 'PMP-0001').
        version: Optional version string ('A.1', 'B.2', etc.). Defaults to latest.

    Returns:
        Part details or error message if not found.
    """
    try:
        clean_pno = validate_part_number(part_number)
    except ValueError as e:
        return {"error": str(e)}

    backend = get_backend()
    part = backend.get_part(part_number=clean_pno, version=version)
    if not part:
        return {"error": f"Part '{clean_pno}' (version: {version or 'latest'}) not found."}
    return part


@mcp.tool()
@audit_tool("search_parts")
def search_parts(
    query: str = "", lifecycle_state: str | None = None, limit: int = 20
) -> list[Part]:
    """Search parts by part number, title, description, or material.

    Args:
        query: Substring to filter across part number, title, description, or material.
        lifecycle_state: Optional lifecycle state filter ('IN_WORK', 'UNDER_REVIEW', 'RELEASED', 'OBSOLETE').
        limit: Maximum number of search results to return (default 20, max 500).

    Returns:
        List of matching Part records, resolving to their latest iteration.
    """
    clean_q = sanitize_text(query, max_length=200, allow_empty=True)
    clean_state = validate_lifecycle_state(lifecycle_state)
    clean_limit = validate_pagination_limit(limit, min_val=1, max_val=500)

    backend = get_backend()
    return backend.search_parts(query=clean_q, lifecycle_state=clean_state, limit=clean_limit)


@mcp.tool()
@audit_tool("get_bom")
def get_bom(part_number: str, levels: int = 1) -> list[BomLink]:
    """Retrieve single-level or multi-level indented Bill of Materials (BOM).

    Uses a recursive Common Table Expression (CTE) to traverse and explode
    the assembly hierarchy up to the requested depth.

    Args:
        part_number: The parent assembly part number (e.g. 'PMP-0001').
        levels: Depth of hierarchy explosion (1 for direct children, max 10 for multi-level).

    Returns:
        List of BomLink records with parent, child, quantity, unit, line find numbers, and level.
    """
    clean_pno = validate_part_number(part_number)
    clean_levels = validate_bom_levels(levels, max_levels=10)

    backend = get_backend()
    return backend.get_bom(part_number=clean_pno, levels=clean_levels)


@mcp.tool()
@audit_tool("where_used")
def where_used(part_number: str, recursive: bool = False) -> list[dict[str, Any]]:
    """Perform where-used analysis to find assemblies that consume this part.

    Uses a recursive CTE when recursive=True to trace components up to root pump assemblies.

    Args:
        part_number: The component part number to look up (e.g. 'PMP-0025').
        recursive: If False, returns direct parent assemblies.
                   If True, recursively traverses all ancestor assemblies up to root products.

    Returns:
        List of consuming parent assembly records with quantities and hierarchy levels.
    """
    clean_pno = validate_part_number(part_number)
    backend = get_backend()
    return backend.where_used(part_number=clean_pno, recursive=recursive)


@mcp.tool()
@audit_tool("compare_boms")
def compare_boms(a: str, b: str) -> BomComparisonResult:
    """Compare two assembly BOM structures or compare EBOM vs. MBOM.

    Args:
        a: First assembly specification (e.g. 'PMP-0001', 'PMP-0001:A.1', or 'PMP-0001:EBOM').
        b: Second assembly specification (e.g. 'PMP-0002', 'PMP-0001:B.1', or 'PMP-0001:MBOM').

    Returns:
        BomComparisonResult detailing added parts, removed parts, and quantity changes.
    """
    backend = get_backend()
    return backend.compare_boms(a=a, b=b)


@mcp.tool()
@audit_tool("find_duplicates")
def find_duplicates() -> list[DuplicateGroup]:
    """Scan part catalog to detect duplicate or near-duplicate component definitions.

    Identifies component proliferation where identical physical specifications,
    materials, and dimensions exist under different part numbers.

    Returns:
        List of DuplicateGroup objects grouping potential redundant parts.
    """
    backend = get_backend()
    res = backend.find_duplicates()
    record_issue_detected("duplicates", len(res))
    return res


@mcp.tool()
@audit_tool("find_obsolete_in_released")
def find_obsolete_in_released() -> list[ObsoleteUsageItem]:
    """Audit released product structures to detect obsolete components.

    Governance check: A RELEASED parent assembly must never reference a child
    component whose lifecycle state is OBSOLETE.

    Returns:
        List of ObsoleteUsageItem records detailing each compliance violation.
    """
    backend = get_backend()
    res = backend.find_obsolete_in_released()
    record_issue_detected("obsolete_in_released", len(res))
    return res


@mcp.tool()
@audit_tool("analyze_change_impact")
def analyze_change_impact(part_number: str) -> ChangeImpactAnalysis:
    """Evaluate cross-functional blast radius of altering or obsoleting a part.

    Analyzes:
    1. Recursive where-used parent assemblies impacted.
    2. Associated engineering documents and CAD drawings requiring revision.
    3. Active change requests already affecting this part.
    4. Approved suppliers and AML sourcing links requiring requalification.
    5. Computes overall impact severity rating (LOW, MEDIUM, HIGH, CRITICAL).

    Args:
        part_number: Part number being analyzed (e.g. 'PMP-0018').

    Returns:
        ChangeImpactAnalysis object detailing the complete system impact.
    """
    backend = get_backend()
    res = backend.analyze_change_impact(part_number=part_number)
    record_impact_analysis(1)
    return res


@mcp.tool()
@audit_tool("draft_change_request")
def draft_change_request(
    title: str,
    affected_parts: list[str],
    reason: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Draft an Engineering Change Request (ECR) documenting a proposed alteration.

    SAFETY GATE:
    - When confirm=False (default): Validates input and returns a DRAFT preview.
      No state change is committed to the database.
    - When confirm=True: Validates and persists the change request to the database,
      assigning an official tracking identifier (e.g. 'CR-XXXX').

    Args:
        title: Descriptive title of the change proposal.
        affected_parts: List of part numbers to link to this change request.
        reason: Detailed justification, failure root cause, or requirement driver.
        confirm: Explicit confirmation gate. Must be True to persist. Defaults to False.

    Returns:
        Dictionary containing draft status, change details, and confirmation message.
    """
    backend = get_backend()

    # Input Validation & Sanitization
    try:
        clean_title = sanitize_text(title, max_length=255, allow_empty=False)
        clean_reason = sanitize_text(reason, max_length=5000, allow_empty=False)
        clean_parts = validate_part_numbers(affected_parts, max_count=50)
    except ValueError as ve:
        return {
            "status": "ERROR",
            "is_persisted": False,
            "error": f"Input validation error: {ve}",
        }

    # Pre-validate affected parts
    invalid_parts = []
    for p_no in clean_parts:
        part = backend.get_part(p_no)
        if not part:
            invalid_parts.append(p_no)

    if invalid_parts:
        return {
            "status": "ERROR",
            "is_persisted": False,
            "error": f"The following affected parts do not exist: {invalid_parts}",
        }

    # Draft Preview Mode (confirm=False)
    if not confirm:
        record_ecr_transition("draft", 1)
        return {
            "status": "DRAFT",
            "is_persisted": False,
            "title": clean_title,
            "affected_parts": clean_parts,
            "reason": clean_reason,
            "message": (
                "DRAFT PREVIEW: Change request validated successfully, but NOT committed to the database. "
                "Set confirm=True to persist this change request."
            ),
        }

    # Confirmed Mutation Mode (confirm=True)
    cr: ChangeRequest = backend.draft_change_request(
        title=clean_title,
        affected_parts=clean_parts,
        reason=clean_reason,
    )
    record_ecr_transition("confirmed", 1)

    return {
        "status": "COMMITTED",
        "is_persisted": True,
        "cr_number": cr.cr_number,
        "title": cr.title,
        "reason": cr.reason,
        "affected_parts": cr.affected_parts,
        "lifecycle_state": cr.status,
        "message": f"Change Request '{cr.cr_number}' successfully created and committed to database.",
    }


# =============================================================================
# ERP Tools (Stock, Open Purchase Orders)
# =============================================================================

@mcp.tool()
@audit_tool("get_erp_stock")
def get_erp_stock(part_number: str) -> ERPInventorySummary | dict[str, str]:
    """Retrieve warehouse stock levels, storage bins, and total inventory valuation for a part.

    Queries connected enterprise ERP systems to calculate aggregate on-hand,
    reserved, and available inventory across all distribution centers and plants.

    Args:
        part_number: Unique part identification number (e.g. 'PMP-0290').

    Returns:
        ERPInventorySummary object detailing stock locations, quantities, and valuation,
        or error message if invalid.
    """
    clean_pno = validate_part_number(part_number)
    backend = get_erp_backend()
    summary = backend.get_stock(part_number=clean_pno)
    return summary


@mcp.tool()
@audit_tool("get_erp_open_pos")
def get_erp_open_pos(part_number: str) -> list[ERPPurchaseOrder]:
    """Retrieve active and open purchase orders with suppliers for a part.

    Identifies procurement commitments, pending vendor shipments, and quantities
    in-transit that may require cancellation, rescheduling, or quarantine.

    Args:
        part_number: Unique part identification number (e.g. 'PMP-0290').

    Returns:
        List of ERPPurchaseOrder records in OPEN, IN_TRANSIT, or HOLD status.
    """
    clean_pno = validate_part_number(part_number)
    backend = get_erp_backend()
    return backend.get_open_pos(part_number=clean_pno)


# =============================================================================
# QMS Tools (Defect Reports & Non-Conformance Records)
# =============================================================================

@mcp.tool()
@audit_tool("get_qms_defects")
def get_qms_defects(
    part_number: str | None = None,
    severity: str | None = None,
    status: str | None = None,
) -> list[QMSDefectReport]:
    """Query quality non-conformance records (NCR) and defect reports linked to part numbers.

    Enables cross-functional quality analysis by correlating field warranty claims,
    dock audit rejects, and lab test failures with engineering components.

    Args:
        part_number: Optional part number filter (e.g. 'PMP-0290').
        severity: Optional severity level ('CRITICAL', 'MAJOR', 'MINOR').
        status: Optional lifecycle status ('OPEN', 'UNDER_INVESTIGATION', 'CONTAINED', etc.).

    Returns:
        List of matching QMSDefectReport records.
    """
    clean_pno = validate_part_number(part_number) if part_number else None
    clean_sev = sanitize_text(severity, max_length=50).upper() if severity else None
    clean_stat = sanitize_text(status, max_length=50).upper() if status else None
    backend = get_qms_backend()
    return backend.get_defects(part_number=clean_pno, severity=clean_sev, status=clean_stat)


@mcp.tool()
@audit_tool("get_qms_defect_report")
def get_qms_defect_report(defect_number: str) -> QMSDefectReport | dict[str, str]:
    """Retrieve full details, root cause, and containment actions for a specific defect report ID.

    Args:
        defect_number: Unique defect tracking code (e.g. 'DEF-2025-0042').

    Returns:
        QMSDefectReport instance or error message if not found.
    """
    clean_defno = sanitize_text(defect_number, max_length=64, allow_empty=False)
    backend = get_qms_backend()
    report = backend.get_defect_by_id(defect_number=clean_defno)
    if not report:
        return {"error": f"QMS Defect Report '{clean_defno}' not found."}
    return report


# =============================================================================
# IIoT Tools (Sensor Failure Events & Asset Telemetry)
# =============================================================================

@mcp.tool()
@audit_tool("get_iiot_failure_events")
def get_iiot_failure_events(
    part_number: str | None = None,
    serial_number: str | None = None,
    severity: str | None = None,
    limit: int = 50,
) -> list[IIoTSensorEvent]:
    """Retrieve real-time field telemetry failure events and sensor anomalies.

    Monitors edge gateways and physical equipment for vibration spikes, thermal
    runaway, pressure drop, or acoustic emission threshold breaches.

    Args:
        part_number: Optional component part number (e.g. 'PMP-0290').
        serial_number: Optional physical asset serial number (e.g. 'SN-APX-2025-001').
        severity: Optional urgency filter ('CRITICAL', 'WARNING', 'INFO').
        limit: Maximum number of events to return (default 50, max 200).

    Returns:
        List of IIoTSensorEvent records describing sensor breaches and anomaly details.
    """
    clean_pno = validate_part_number(part_number) if part_number else None
    clean_sn = sanitize_text(serial_number, max_length=64) if serial_number else None
    clean_sev = sanitize_text(severity, max_length=50).upper() if severity else None
    clean_limit = validate_pagination_limit(limit, min_val=1, max_val=200)

    backend = get_iiot_backend()
    return backend.get_failure_events(
        part_number=clean_pno,
        serial_number=clean_sn,
        severity=clean_sev,
        limit=clean_limit,
    )


@mcp.tool()
@audit_tool("get_iiot_device_telemetry")
def get_iiot_device_telemetry(serial_number: str) -> IIoTDevice | dict[str, str]:
    """Retrieve edge gateway health, installation metadata, and operating location for an asset.

    Args:
        serial_number: Asset equipment serial number (e.g. 'SN-APX-2025-001').

    Returns:
        IIoTDevice record or error message if not found.
    """
    clean_sn = sanitize_text(serial_number, max_length=64, allow_empty=False)
    backend = get_iiot_backend()
    device = backend.get_device(serial_number=clean_sn)
    if not device:
        return {"error": f"IIoT Device for serial number '{clean_sn}' not found."}
    return device


def main():
    """Run FastMCP server on stdio transport."""
    mcp.run()


if __name__ == "__main__":
    main()

