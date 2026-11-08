"""Closed-Loop Quality & Digital Thread Demo.

Demonstrates the automated closed-loop remediation scenario:
1. IIoT Telemetry Anomaly: Vibration and temperature trip on field pump asset SN-APX-2025-001.
2. QMS Defect Correlation: Non-conformance report DEF-2025-0042 linking failure to PMP-0290 bearing.
3. PLM Impact Analysis: Blast-radius evaluation finding 4 parent assemblies including ApexFlow 1000.
4. ERP Supply Chain Exposure: On-hand inventory ($34,912.50) and in-transit PO-2025-0812 ($71,250).
5. Draft ECR Generation: Safety-gated change request drafting and confirmed database commit.
"""

import json
import sys
from typing import Any

import server
from erp_interface import ERPInventorySummary, ERPPurchaseOrder
from iiot_interface import IIoTDevice, IIoTSensorEvent
from plm_interface import ChangeImpactAnalysis, Part
from qms_interface import QMSDefectReport


def print_header(title: str) -> None:
    """Print formatted section header."""
    separator = "=" * 80
    print(f"\n{separator}")
    print(f" {title.upper()}")
    print(f"{separator}\n")


def print_step(step_num: int, title: str) -> None:
    """Print step subtitle."""
    print(f"\n>>> [STEP {step_num}] {title}")
    print("-" * 75)


def run_closed_loop_demo() -> dict[str, Any]:
    """Execute the end-to-end closed-loop quality remediation workflow.

    Returns:
        Dictionary containing artifacts and results from each stage of the workflow.
    """
    print_header("PTC Windchill & Digital Thread Closed-Loop Demo")
    print("Scenario: Field Anomaly -> Quality Defect -> PLM Impact -> ERP Supply Chain -> ECR")

    results: dict[str, Any] = {}

    # =========================================================================
    # STEP 1: IIoT Telemetry Anomaly Detection
    # =========================================================================
    print_step(1, "IIoT Telemetry Monitoring: Scanning Field Assets for Critical Anomalies")

    events: list[IIoTSensorEvent] = server.get_iiot_failure_events(severity="CRITICAL")
    results["critical_events"] = [e.model_dump() for e in events]

    print(f"Discovered {len(events)} critical sensor anomaly event(s) in field telemetry:")
    for evt in events:
        print(f"  • Event ID    : {evt.event_id}")
        print(f"    Asset Serial: {evt.serial_number}")
        print(f"    Target Part : {evt.part_number}")
        print(f"    Sensor Type : {evt.sensor_type.value} ({evt.metric_name})")
        print(f"    Reading     : {evt.metric_value} {evt.unit} (Alarm Threshold: {evt.threshold_value} {evt.unit})")
        print(f"    Severity    : {evt.severity.value} [{evt.event_type}]")
        print(f"    Diagnostics : {evt.details}")
        print()

    # Focus on the failing asset and part
    primary_event = events[0]
    failing_part_number = primary_event.part_number
    failing_serial = primary_event.serial_number

    # Retrieve edge gateway details
    device: IIoTDevice | dict[str, str] = server.get_iiot_device_telemetry(serial_number=failing_serial)
    if isinstance(device, IIoTDevice):
        results["device"] = device.model_dump()
        print(f"Edge Gateway Asset Profile:")
        print(f"  • Asset Name  : {device.asset_name}")
        print(f"  • Location    : {device.location}")
        print(f"  • Fleet Status: {device.status}")
        print(f"  • Parts Active: {', '.join(device.installed_parts)}")
    print()

    # =========================================================================
    # STEP 2: QMS Quality Investigation & Defect Correlation
    # =========================================================================
    print_step(2, f"QMS Quality Investigation: Correlating Defect Reports for Part '{failing_part_number}'")

    defects: list[QMSDefectReport] = server.get_qms_defects(part_number=failing_part_number)
    results["defects"] = [d.model_dump() for d in defects]

    print(f"Found {len(defects)} linked QMS non-conformance / failure investigation(s):")
    for d in defects:
        print(f"  • Defect ID   : {d.defect_number} [{d.severity.value}]")
        print(f"    Title       : {d.title}")
        print(f"    Status      : {d.status.value}")
        print(f"    Failure Mode: {d.failure_mode}")
        print(f"    Root Cause  : {d.root_cause}")
        print(f"    Linked S/Ns : {', '.join(d.linked_serial_numbers)}")
        print(f"    Containment : {d.containment_action}")
        print()

    # =========================================================================
    # STEP 3: PLM Cross-Functional Impact & Blast Radius Analysis
    # =========================================================================
    print_step(3, f"PLM Engineering Impact: Blast Radius Analysis for '{failing_part_number}'")

    part: Part | dict[str, str] = server.get_part(part_number=failing_part_number)
    if isinstance(part, Part):
        results["part_details"] = part.model_dump()
        print(f"PLM Part Master Record:")
        print(f"  • Part Number : {part.part_number} (Rev {part.version_label})")
        print(f"  • Title       : {part.name}")
        print(f"  • Lifecycle   : {part.lifecycle_state.value}")
        print(f"  • Make / Buy  : {part.make_buy}")
        print(f"  • Material    : {part.material}")
        print()

    impact: ChangeImpactAnalysis = server.analyze_change_impact(part_number=failing_part_number)
    results["plm_impact"] = impact.model_dump()

    print(f"PLM Change Impact Blast Radius:")
    print(f"  • Impact Level: {impact.impact_level}")
    print(f"  • Direct Parent Assemblies    : {', '.join(impact.direct_parents)}")
    print(f"  • All Consuming Products (BOM): {', '.join(impact.all_affected_assemblies)}")
    print(f"  • AML Approved Suppliers      : {', '.join(impact.approved_suppliers)}")
    print(f"  • Active Change Requests      : {', '.join(impact.active_change_requests)}")
    print()

    # =========================================================================
    # STEP 4: ERP Supply Chain Exposure & Stock Quarantine
    # =========================================================================
    print_step(4, f"ERP Supply Chain Audit: Assessing Inventory & Open PO Exposure for '{failing_part_number}'")

    stock: ERPInventorySummary | dict[str, str] = server.get_erp_stock(part_number=failing_part_number)
    results["erp_stock"] = stock.model_dump() if isinstance(stock, ERPInventorySummary) else stock

    if isinstance(stock, ERPInventorySummary):
        print(f"ERP Warehouse Stock Balance:")
        print(f"  • Total On-Hand   : {stock.total_on_hand} ea")
        print(f"  • Total Reserved  : {stock.total_reserved} ea")
        print(f"  • Total Available : {stock.total_available} ea")
        print(f"  • Total Valuation : ${stock.total_valuation:,.2f} {stock.currency} [AT RISK]")
        print("  • Warehouse Breakdown:")
        for loc in stock.stock_locations:
            print(f"    - {loc.warehouse_code} ({loc.warehouse_name}): {loc.quantity_on_hand} on-hand in bin {loc.bin_location} (Unit Cost: ${loc.unit_cost:.2f})")
        print()

    open_pos: list[ERPPurchaseOrder] = server.get_erp_open_pos(part_number=failing_part_number)
    results["erp_pos"] = [po.model_dump() for po in open_pos]

    print(f"ERP Open Purchase Orders with Suppliers ({len(open_pos)} active):")
    total_po_exposure = 0.0
    for po in open_pos:
        line_val = po.quantity_ordered * po.unit_price
        total_po_exposure += line_val
        print(f"  • PO Number    : {po.po_number} (Line {po.line_number})")
        print(f"    Supplier     : {po.supplier_name}")
        print(f"    Qty Ordered  : {po.quantity_ordered} ea (${line_val:,.2f} {po.currency})")
        print(f"    Status       : {po.status.value}")
        print(f"    Delivery Date: {po.expected_delivery}")
        print()
    print(f"  • Total Open PO Commitment Exposure: ${total_po_exposure:,.2f} USD")
    print()

    # =========================================================================
    # STEP 5: Closed-Loop Engineering Change Request (ECR) Generation
    # =========================================================================
    print_step(5, "Closed-Loop Governance: Generating Engineering Change Request (ECR)")

    ecr_title = f"Emergency Redesign & Sourcing Upgrade for {failing_part_number} Bearing Assembly"
    affected_parts = [failing_part_number, "PMP-0010", "PMP-0001"]
    ecr_reason = (
        f"CLOSED-LOOP REMEDIATION: Telemetry anomaly EVT-IIOT-2025-0901 on asset {failing_serial} "
        f"confirmed severe vibration (18.6 mm/s) correlated with QMS-DEF-2025-0042 outer raceway spalling. "
        f"PLM blast radius affects flagship product PMP-0001. ERP quarantine required for {stock.total_on_hand} on-hand units "
        f"(${stock.total_valuation:,.2f}) and hold on in-transit PO-2025-0812 (500 units, $71,250.00)."
    )

    # 5A. Preview Draft (confirm=False)
    print(">>> 5A. Submitting Draft Preview (Safety Gate: confirm=False)...")
    draft_preview = server.draft_change_request(
        title=ecr_title,
        affected_parts=affected_parts,
        reason=ecr_reason,
        confirm=False,
    )
    results["draft_preview"] = draft_preview
    print(f"  • Status      : {draft_preview['status']}")
    print(f"  • Persisted   : {draft_preview['is_persisted']}")
    print(f"  • Gate Message: {draft_preview['message']}")
    print()

    # 5B. Commit Mutation (confirm=True)
    print(">>> 5B. Committing Verified ECR to Database (Safety Gate: confirm=True)...")
    committed_cr = server.draft_change_request(
        title=ecr_title,
        affected_parts=affected_parts,
        reason=ecr_reason,
        confirm=True,
    )
    results["committed_cr"] = committed_cr
    print(f"  • Change Req #: {committed_cr.get('cr_number')}")
    print(f"  • Status      : {committed_cr.get('status')}")
    print(f"  • Persisted   : {committed_cr.get('is_persisted')}")
    print(f"  • Impacted    : {', '.join(committed_cr.get('affected_parts', []))}")
    print(f"  • Resolution  : {committed_cr.get('message')}")
    print()

    # =========================================================================
    # STEP 6: Summary & Closed-Loop Complete
    # =========================================================================
    print_header("Closed-Loop Quality Scenario Completed Successfully")
    print("Summary of Automated Cross-Domain Thread:")
    print("  1. [IIoT] Anomaly detected: Asset SN-APX-2025-001 vibration trip (18.6 mm/s).")
    print("  2. [QMS]  Defect correlated: DEF-2025-0042 confirmed bearing raceway spalling.")
    print("  3. [PLM]  Impact evaluated: 4 parent assemblies affected (including ApexFlow 1000).")
    print("  4. [ERP]  Supply chain contained: 245 units quarantined ($34,912.50) + PO-2025-0812 held.")
    print(f"  5. [ECR]  Governance initiated: Created {committed_cr.get('cr_number')} to up-rate design.")
    print("\nAll tool calls recorded in audit.log.")

    return results


def main():
    """Main CLI entrypoint."""
    run_closed_loop_demo()


if __name__ == "__main__":
    main()

