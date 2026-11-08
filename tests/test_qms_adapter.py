"""Tests for QMS models and MockQMSBackend."""

import pytest
from mock_qms_backend import MockQMSBackend
from qms_interface import (
    DefectSeverity,
    DefectStatus,
    QMSDefectReport,
)


@pytest.fixture
def qms_backend():
    return MockQMSBackend(db_path="plm_mock.db")


def test_qms_defect_report_model():
    report = QMSDefectReport(
        defect_number="DEF-001",
        part_number="PMP-0290",
        title="Spalling defect",
        description="Detailed description",
        severity=DefectSeverity.CRITICAL,
        status=DefectStatus.UNDER_INVESTIGATION,
        failure_mode="SURFACE_SPALLING",
        reported_by="Reliability Eng",
    )
    assert report.defect_number == "DEF-001"
    assert report.severity == DefectSeverity.CRITICAL
    assert report.status == DefectStatus.UNDER_INVESTIGATION


def test_qms_get_defects_by_part(qms_backend):
    defects = qms_backend.get_defects(part_number="PMP-0290")
    assert len(defects) == 1
    defect = defects[0]
    assert defect.defect_number == "DEF-2025-0042"
    assert defect.severity == DefectSeverity.CRITICAL
    assert defect.status == DefectStatus.UNDER_INVESTIGATION
    assert "SN-APX-2025-001" in defect.linked_serial_numbers


def test_qms_get_defects_filtered(qms_backend):
    critical_defects = qms_backend.get_defects(severity="CRITICAL")
    assert len(critical_defects) >= 1
    assert all(d.severity == DefectSeverity.CRITICAL for d in critical_defects)

    open_defects = qms_backend.get_defects(status="OPEN")
    assert len(open_defects) >= 1
    assert all(d.status == DefectStatus.OPEN for d in open_defects)


def test_qms_get_defect_by_id(qms_backend):
    defect = qms_backend.get_defect_by_id("DEF-2025-0042")
    assert defect is not None
    assert defect.part_number == "PMP-0290"
    assert defect.failure_mode == "SURFACE_SPALLING"

    missing = qms_backend.get_defect_by_id("NON_EXISTENT_DEFECT")
    assert missing is None

