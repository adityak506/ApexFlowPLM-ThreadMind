"""Tests for server.py FastMCP tool registrations, safety gate, backend switching, and audit logging."""

import json
import os
import pytest
from server import (
    AUDIT_LOG_FILE,
    analyze_change_impact,
    compare_boms,
    draft_change_request,
    find_duplicates,
    find_obsolete_in_released,
    get_backend,
    get_bom,
    get_part,
    mcp,
    search_parts,
    where_used,
)
from seed_data import generate_dataset


@pytest.fixture(autouse=True)
def setup_test_env(tmp_path, monkeypatch):
    """Setup isolated test database and audit log for each test."""
    db_file = str(tmp_path / "test_server_plm.db")
    audit_file = str(tmp_path / "test_audit.log")

    generate_dataset(db_path=db_file)

    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setenv("PLM_SQLITE_PATH", db_file)
    monkeypatch.setattr("server.AUDIT_LOG_FILE", audit_file)

    yield {
        "db_file": db_file,
        "audit_file": audit_file,
    }


def test_mcp_server_registered_tools():
    """Verify that all required tools are registered with FastMCP."""
    tools = mcp._tool_manager.list_tools()
    registered_names = {t.name for t in tools}

    expected_tools = {
        "search_parts",
        "get_part",
        "get_bom",
        "where_used",
        "compare_boms",
        "find_duplicates",
        "find_obsolete_in_released",
        "analyze_change_impact",
        "draft_change_request",
        "get_erp_stock",
        "get_erp_open_pos",
        "get_qms_defects",
        "get_qms_defect_report",
        "get_iiot_failure_events",
        "get_iiot_device_telemetry",
    }
    for t_name in expected_tools:
        assert t_name in registered_names, f"Tool '{t_name}' not registered on FastMCP server"


def test_dynamic_backend_selection(monkeypatch):
    """Verify backend factory switches between MockBackend and WindchillBackend."""
    monkeypatch.setenv("PLM_BACKEND", "mock")
    b_mock = get_backend()
    assert b_mock.__class__.__name__ == "MockBackend"

    monkeypatch.setenv("PLM_BACKEND", "windchill")
    b_wc = get_backend()
    assert b_wc.__class__.__name__ == "WindchillBackend"


def test_draft_change_request_safety_gate(setup_test_env):
    """Verify draft_change_request creates DRAFT only unless confirm=True."""
    audit_file = setup_test_env["audit_file"]

    # 1. Draft Mode (confirm=False)
    draft_res = draft_change_request(
        title="Upgrade impeller face",
        affected_parts=["PMP-0001"],
        reason="Performance optimization",
        confirm=False,
    )
    assert draft_res["status"] == "DRAFT"
    assert draft_res["is_persisted"] is False
    assert "DRAFT PREVIEW" in draft_res["message"]

    # Verify not written to database
    b = get_backend()
    search_cr = b._conn.execute("SELECT * FROM change_requests WHERE title = 'Upgrade impeller face'").fetchall()
    assert len(search_cr) == 0

    # 2. Confirmed Mode (confirm=True)
    live_res = draft_change_request(
        title="Upgrade impeller face",
        affected_parts=["PMP-0001"],
        reason="Performance optimization",
        confirm=True,
    )
    assert live_res["status"] == "COMMITTED"
    assert live_res["is_persisted"] is True
    assert live_res["cr_number"].startswith("CR-")

    # Verify written to database
    search_cr_after = b._conn.execute("SELECT * FROM change_requests WHERE title = 'Upgrade impeller face'").fetchall()
    assert len(search_cr_after) == 1


def test_structured_audit_logging(setup_test_env):
    """Verify that every tool call appends a structured entry to audit.log."""
    audit_file = setup_test_env["audit_file"]

    # Call several tools
    search_parts(query="ApexFlow", limit=5)
    get_bom(part_number="PMP-0001", levels=1)
    where_used(part_number="PMP-0025", recursive=False)
    find_duplicates()
    find_obsolete_in_released()
    analyze_change_impact(part_number="PMP-0018")

    assert os.path.exists(audit_file)

    with open(audit_file, "r", encoding="utf-8") as f:
        log_lines = [json.loads(line) for line in f if line.strip()]

    assert len(log_lines) >= 6

    # Verify schema of each log line
    tools_called = set()
    for entry in log_lines:
        assert "timestamp" in entry
        assert "tool" in entry
        assert "args" in entry
        assert "status" in entry
        assert "result_count" in entry
        assert entry["status"] == "SUCCESS"
        assert entry["result_count"] >= 0
        tools_called.add(entry["tool"])

    assert "search_parts" in tools_called
    assert "get_bom" in tools_called
    assert "where_used" in tools_called
    assert "find_duplicates" in tools_called
    assert "find_obsolete_in_released" in tools_called
    assert "analyze_change_impact" in tools_called

