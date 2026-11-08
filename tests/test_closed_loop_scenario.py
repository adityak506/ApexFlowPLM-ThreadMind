"""Integration test for closed-loop quality remediation scenario."""

import pytest
from demo_closed_loop import run_closed_loop_demo
from seed_data import generate_dataset


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Setup isolated test database and audit log for each test."""
    db_file = str(tmp_path / "test_closed_loop.db")
    audit_file = str(tmp_path / "test_closed_loop_audit.log")

    generate_dataset(db_path=db_file)

    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setenv("PLM_SQLITE_PATH", db_file)
    monkeypatch.setattr("server.AUDIT_LOG_FILE", audit_file)

    yield {
        "db_file": db_file,
        "audit_file": audit_file,
    }


def test_closed_loop_workflow_execution():
    """Verify that the closed-loop scenario runs cleanly through all 5 stages."""
    result = run_closed_loop_demo()

    # Step 1: IIoT
    assert "critical_events" in result
    assert len(result["critical_events"]) >= 1
    assert result["critical_events"][0]["part_number"] == "PMP-0290"
    assert result["device"]["serial_number"] == "SN-APX-2025-001"

    # Step 2: QMS
    assert "defects" in result
    assert len(result["defects"]) >= 1
    assert result["defects"][0]["defect_number"] == "DEF-2025-0042"

    # Step 3: PLM
    assert "plm_impact" in result
    assert result["plm_impact"]["impact_level"] == "HIGH"
    assert "PMP-0001" in result["plm_impact"]["all_affected_assemblies"]

    # Step 4: ERP
    assert "erp_stock" in result
    assert result["erp_stock"]["total_on_hand"] == 245.0
    assert result["erp_stock"]["total_available"] == 200.0
    assert len(result["erp_pos"]) >= 2

    # Step 5: ECR
    assert result["draft_preview"]["is_persisted"] is False
    assert result["committed_cr"]["is_persisted"] is True
    assert result["committed_cr"]["status"] == "COMMITTED"
    assert result["committed_cr"]["cr_number"].startswith("CR-")
