"""Tests verifying cross-domain MCP tools exposed on FastMCP server."""

import pytest
from erp_interface import ERPInventorySummary, ERPPurchaseOrder
from iiot_interface import IIoTDevice, IIoTSensorEvent
from qms_interface import QMSDefectReport
from seed_data import generate_dataset
import server


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Setup isolated test database and audit log for each test."""
    db_file = str(tmp_path / "test_cross_domain.db")
    audit_file = str(tmp_path / "test_cross_audit.log")

    generate_dataset(db_path=db_file)

    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setenv("PLM_SQLITE_PATH", db_file)
    monkeypatch.setattr("server.AUDIT_LOG_FILE", audit_file)

    yield {
        "db_file": db_file,
        "audit_file": audit_file,
    }


def test_server_get_erp_stock():
    res = server.get_erp_stock(part_number="PMP-0290")
    assert isinstance(res, ERPInventorySummary)
    assert res.part_number == "PMP-0290"
    assert res.total_on_hand == 245.0
    assert res.total_available == 200.0


def test_server_get_erp_open_pos():
    pos = server.get_erp_open_pos(part_number="PMP-0290")
    assert isinstance(pos, list)
    assert len(pos) >= 2
    assert all(isinstance(p, ERPPurchaseOrder) for p in pos)


def test_server_get_qms_defects():
    defects = server.get_qms_defects(part_number="PMP-0290")
    assert isinstance(defects, list)
    assert len(defects) == 1
    assert isinstance(defects[0], QMSDefectReport)
    assert defects[0].defect_number == "DEF-2025-0042"


def test_server_get_qms_defect_report():
    report = server.get_qms_defect_report(defect_number="DEF-2025-0042")
    assert isinstance(report, QMSDefectReport)
    assert report.defect_number == "DEF-2025-0042"

    not_found = server.get_qms_defect_report(defect_number="DEF-9999-9999")
    assert isinstance(not_found, dict)
    assert "error" in not_found


def test_server_get_iiot_failure_events():
    events = server.get_iiot_failure_events(part_number="PMP-0290", severity="CRITICAL")
    assert isinstance(events, list)
    assert len(events) == 2
    assert all(isinstance(e, IIoTSensorEvent) for e in events)


def test_server_get_iiot_device_telemetry():
    device = server.get_iiot_device_telemetry(serial_number="SN-APX-2025-001")
    assert isinstance(device, IIoTDevice)
    assert device.device_id == "EDGE-GATEWAY-101"

    not_found = server.get_iiot_device_telemetry(serial_number="SN-UNKNOWN")
    assert isinstance(not_found, dict)
    assert "error" in not_found
