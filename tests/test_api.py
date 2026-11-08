"""Pytest suite for Mock PLM FastAPI REST API (api.py).

Verifies all REST endpoints using FastAPI TestClient:
- GET /parts (search, filter, pagination)
- GET /parts/{number} (lookup, 404 handling)
- GET /parts/{number}/bom (single and multi-level explosion, 404, validation)
- GET /parts/{number}/where-used (direct and recursive traversal, 404)
- POST /bom/compare (assembly diffing, EBOM vs MBOM)
- GET /issues/summary (planted data quality metrics)
- GET /issues/{type} (specific issue details, pagination, invalid type handling)
- POST /impact (blast radius calculation, 404)
- GET /changes (change request listing, pagination, state filtering)
- POST /changes/draft & POST /changes/{id}/confirm (two-step write safety gate)
- Consistent error formatting (404, 400, 422)
- CORS headers for localhost:5173
- Backend selection via PLM_BACKEND
"""

import os
import tempfile
import pytest
from fastapi.testclient import TestClient

from api import (
    app,
    PENDING_DRAFTS,
    get_backend,
    get_erp_backend,
    get_qms_backend,
    get_iiot_backend,
)
from mock_backend import MockBackend
from mock_erp_backend import MockERPBackend
from mock_qms_backend import MockQMSBackend
from mock_iiot_backend import MockIIoTBackend
from seed_data import generate_dataset
from windchill_backend import WindchillBackend


@pytest.fixture(scope="module")
def test_client():
    """Create a persistent seeded test database and TestClient instance."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp_dir:
        test_db = os.path.join(tmp_dir, "test_api_plm.db")
        generate_dataset(db_path=test_db)
        
        orig_plm_sqlite = os.environ.get("PLM_SQLITE_PATH")
        os.environ["PLM_SQLITE_PATH"] = test_db

        # Override backend dependencies to point to the isolated test database
        test_backend = MockBackend(db_path=test_db)
        erp_backend = MockERPBackend(db_path=test_db)
        qms_backend = MockQMSBackend(db_path=test_db)
        iiot_backend = MockIIoTBackend(db_path=test_db)
        app.dependency_overrides[get_backend] = lambda: test_backend
        app.dependency_overrides[get_erp_backend] = lambda: erp_backend
        app.dependency_overrides[get_qms_backend] = lambda: qms_backend
        app.dependency_overrides[get_iiot_backend] = lambda: iiot_backend
        
        with TestClient(app) as client:
            yield client
            
        app.dependency_overrides.clear()
        test_backend.close()
        erp_backend.close()
        qms_backend.close()
        iiot_backend.close()

        if orig_plm_sqlite is not None:
            os.environ["PLM_SQLITE_PATH"] = orig_plm_sqlite
        else:
            os.environ.pop("PLM_SQLITE_PATH", None)


@pytest.fixture(autouse=True)
def clear_drafts():
    """Ensure in-memory pending drafts are clean between tests."""
    PENDING_DRAFTS.clear()
    yield
    PENDING_DRAFTS.clear()


# =============================================================================
# 1. Part Catalog Tests (GET /parts, GET /parts/{number})
# =============================================================================

def test_list_parts_default(test_client: TestClient):
    """Test listing parts with default pagination."""
    response = test_client.get("/parts")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total"] > 0
    assert len(data["items"]) == 20
    assert data["total_pages"] >= 1


def test_list_parts_with_filters_and_pagination(test_client: TestClient):
    """Test searching parts by query, lifecycle state, and pagination."""
    response = test_client.get("/parts?query=ApexFlow&lifecycle_state=RELEASED&page=1&page_size=5")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 5
    assert data["page"] == 1
    assert data["page_size"] == 5
    for item in data["items"]:
        assert item["lifecycle_state"] == "RELEASED"
        assert "apexflow" in item["name"].lower() or "apexflow" in item["part_number"].lower()


def test_list_parts_invalid_pagination(test_client: TestClient):
    """Test that invalid pagination parameters return 422 with consistent error format."""
    response = test_client.get("/parts?page=0&page_size=-5")
    assert response.status_code == 422
    data = response.json()
    assert data["error"] == "ValidationError"
    assert "Invalid request" in data["message"]
    assert isinstance(data["detail"], list)


def test_get_part_by_number_success(test_client: TestClient):
    """Test retrieving an existing part by number."""
    response = test_client.get("/parts/PMP-0001")
    assert response.status_code == 200
    data = response.json()
    assert data["part_number"] == "PMP-0001"
    assert "ApexFlow" in data["name"]
    assert data["revision"] is not None
    assert data["iteration"] is not None


def test_get_part_by_number_not_found(test_client: TestClient):
    """Test 404 response for non-existent part with consistent error format."""
    response = test_client.get("/parts/PMP-9999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NotFound"
    assert "PMP-9999" in data["message"]


# =============================================================================
# 2. BOM & Where-Used Tests (GET /parts/{number}/bom, GET /parts/{number}/where-used)
# =============================================================================

def test_get_part_bom_single_level(test_client: TestClient):
    """Test single-level BOM explosion."""
    response = test_client.get("/parts/PMP-0001/bom?levels=1")
    assert response.status_code == 200
    links = response.json()
    assert isinstance(links, list)
    assert len(links) > 0
    for link in links:
        assert link["parent_part_number"] == "PMP-0001"
        assert link["level"] == 1
        assert link["quantity"] > 0


def test_get_part_bom_multi_level(test_client: TestClient):
    """Test multi-level BOM explosion contains deeper levels."""
    response = test_client.get("/parts/PMP-0001/bom?levels=3")
    assert response.status_code == 200
    links = response.json()
    levels = {link["level"] for link in links}
    assert 1 in levels
    assert len(links) >= len(test_client.get("/parts/PMP-0001/bom?levels=1").json())


def test_get_part_bom_not_found(test_client: TestClient):
    """Test BOM query on non-existent assembly returns 404."""
    response = test_client.get("/parts/PMP-9999/bom?levels=1")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NotFound"


def test_get_part_where_used(test_client: TestClient):
    """Test finding consuming parent assemblies."""
    response = test_client.get("/parts/PMP-0290/where-used?recursive=false")
    assert response.status_code == 200
    records = response.json()
    assert isinstance(records, list)
    assert len(records) > 0
    for rec in records:
        assert "parent_part_number" in rec
        assert "quantity" in rec


def test_get_part_where_used_recursive(test_client: TestClient):
    """Test recursive where-used traversal finds root assembly."""
    response = test_client.get("/parts/PMP-0290/where-used?recursive=true")
    assert response.status_code == 200
    records = response.json()
    parent_numbers = [r["parent_part_number"] for r in records]
    assert any("PMP-000" in p for p in parent_numbers)


def test_get_part_where_used_not_found(test_client: TestClient):
    """Test where-used on non-existent part returns 404."""
    response = test_client.get("/parts/PMP-9999/where-used")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NotFound"


# =============================================================================
# 3. BOM Comparison Tests (POST /bom/compare)
# =============================================================================

def test_compare_boms_success(test_client: TestClient):
    """Test comparing two distinct assembly BOMs."""
    payload = {
        "assembly_a": "PMP-0001",
        "assembly_b": "PMP-0002",
    }
    response = test_client.post("/bom/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["assembly_a"] == "PMP-0001"
    assert data["assembly_b"] == "PMP-0002"
    assert "differences" in data
    assert "added_parts" in data
    assert "removed_parts" in data


def test_compare_ebom_vs_mbom(test_client: TestClient):
    """Test comparing EBOM vs MBOM for the same assembly."""
    payload = {
        "assembly_a": "PMP-0001:EBOM",
        "assembly_b": "PMP-0001:MBOM",
    }
    response = test_client.post("/bom/compare", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "differences" in data


# =============================================================================
# 4. Planted Issues Diagnostics (GET /issues/summary, GET /issues/{type})
# =============================================================================

def test_get_issues_summary(test_client: TestClient):
    """Test aggregate issues summary returns counts for all 5 planted issues."""
    response = test_client.get("/issues/summary")
    assert response.status_code == 200
    data = response.json()
    assert data["duplicates"] == 5
    assert data["obsolete_in_released"] == 8
    assert data["unassigned_buy"] == 12
    assert data["ebom_mbom_mismatches"] == 5
    assert data["rohs_risks"] == 6
    assert data["total_issues"] == 36


@pytest.mark.parametrize(
    "issue_type, expected_min_count",
    [
        ("duplicates", 5),
        ("obsolete_in_released", 8),
        ("unassigned_buy", 12),
        ("ebom_mbom_mismatches", 5),
        ("rohs_risks", 6),
    ],
)
def test_get_issues_by_type_success(test_client: TestClient, issue_type: str, expected_min_count: int):
    """Test retrieving details and items for each supported issue type."""
    response = test_client.get(f"/issues/{issue_type}?page=1&page_size=20")
    assert response.status_code == 200
    data = response.json()
    assert data["issue_type"] == issue_type
    assert data["total"] >= expected_min_count
    assert len(data["items"]) > 0


def test_get_issues_by_type_invalid(test_client: TestClient):
    """Test requesting an unsupported issue type returns 400 with consistent error format."""
    response = test_client.get("/issues/unsupported_issue_type")
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "BadRequest"
    assert "Unsupported issue type" in data["message"]


# =============================================================================
# 5. Change Impact Analysis (POST /impact)
# =============================================================================

def test_analyze_impact_success(test_client: TestClient):
    """Test change blast-radius analysis on an existing part."""
    payload = {"part_number": "PMP-0010"}
    response = test_client.post("/impact", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["target_part_number"] == "PMP-0010"
    assert "direct_parents" in data
    assert "all_affected_assemblies" in data
    assert data["impact_level"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")


def test_analyze_impact_not_found(test_client: TestClient):
    """Test blast-radius analysis on non-existent part returns 404."""
    payload = {"part_number": "PMP-9999"}
    response = test_client.post("/impact", json=payload)
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NotFound"


# =============================================================================
# 6. Change Management & Two-Step Safety Gate Tests
#    (GET /changes, POST /changes/draft, POST /changes/{id}/confirm)
# =============================================================================

def test_list_change_requests(test_client: TestClient):
    """Test retrieving existing committed change requests."""
    response = test_client.get("/changes?page=1&page_size=10")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert data["page"] == 1
    assert data["total"] > 0


def test_two_step_draft_and_confirm_lifecycle(test_client: TestClient):
    """Verify write safety: draft is not persisted until explicit confirmation."""
    # Step 1: Record initial change request count
    initial_res = test_client.get("/changes?page=1&page_size=1")
    initial_total = initial_res.json()["total"]

    # Step 2: Create a draft change request
    draft_payload = {
        "title": "Upgrade Bearing Tolerance to ABEC-7",
        "affected_parts": ["PMP-0290"],
        "reason": "Excessive vibration detected under high cavitation loading.",
        "category": "DESIGN_IMPROVEMENT",
        "priority": "HIGH",
    }
    draft_res = test_client.post("/changes/draft", json=draft_payload)
    assert draft_res.status_code == 200
    draft_data = draft_res.json()
    assert draft_data["status"] == "DRAFT"
    assert draft_data["is_persisted"] is False
    draft_id = draft_data["draft_id"]
    assert draft_id.startswith("DRAFT-")

    # Step 3: Verify the database was NOT modified
    after_draft_res = test_client.get("/changes?page=1&page_size=1")
    assert after_draft_res.json()["total"] == initial_total

    # Step 4: Confirm the draft explicitly
    confirm_res = test_client.post(f"/changes/{draft_id}/confirm")
    assert confirm_res.status_code == 201
    confirm_data = confirm_res.json()
    assert confirm_data["status"] == "OPEN"
    assert confirm_data["is_persisted"] is True
    assert confirm_data["cr_number"].startswith("CR-")

    # Step 5: Verify the database now reflects the confirmed change request
    after_confirm_res = test_client.get("/changes?page=1&page_size=1")
    assert after_confirm_res.json()["total"] == initial_total + 1

    # Step 6: Verify confirming the same draft again returns 404
    duplicate_confirm_res = test_client.post(f"/changes/{draft_id}/confirm")
    assert duplicate_confirm_res.status_code == 404
    assert duplicate_confirm_res.json()["error"] == "NotFound"


def test_draft_change_validation_nonexistent_part(test_client: TestClient):
    """Test drafting a change with a non-existent part returns 400."""
    payload = {
        "title": "Invalid Part Change",
        "affected_parts": ["PMP-9999"],
        "reason": "Testing invalid part error handling",
    }
    response = test_client.post("/changes/draft", json=payload)
    assert response.status_code == 400
    data = response.json()
    assert data["error"] == "BadRequest"
    assert "PMP-9999" in data["message"]


def test_confirm_nonexistent_draft_id(test_client: TestClient):
    """Test confirming a random draft ID returns 404."""
    response = test_client.post("/changes/DRAFT-NONEXISTENT/confirm")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NotFound"


# =============================================================================
# 7. CORS Headers & Backend Selection Configuration
# =============================================================================

def test_cors_headers(test_client: TestClient):
    """Verify CORS headers are returned for localhost:5173 origin."""
    response = test_client.get("/parts", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_backend_selection_env(monkeypatch):
    """Verify get_backend dynamically chooses backend from PLM_BACKEND env var."""
    monkeypatch.setenv("PLM_BACKEND", "windchill")
    backend = get_backend()
    assert isinstance(backend, WindchillBackend)

    monkeypatch.setenv("PLM_BACKEND", "mock")
    backend_mock = get_backend()
    assert isinstance(backend_mock, MockBackend)


# =============================================================================
# 8. AI Assistant Chat Endpoint (POST /chat)
# =============================================================================

def test_chat_endpoint_obsolete_tool_calling(test_client: TestClient):
    """Test AI chat stream invokes find_obsolete_in_released tool."""
    payload = {
        "message": "Find obsolete parts in released BOMs",
        "history": [],
    }
    response = test_client.post("/chat", json=payload)
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    body = response.text
    assert "event: tool_call" in body
    assert "find_obsolete_in_released" in body
    assert "event: tool_result" in body
    assert "event: content_delta" in body
    assert "event: done" in body
    assert "compliance violations" in body.lower() or "obsolete" in body.lower()


def test_chat_endpoint_impact_tool_calling(test_client: TestClient):
    """Test AI chat stream invokes analyze_change_impact tool for part."""
    payload = {
        "message": "What is the change impact of part PMP-0010?",
        "history": [],
    }
    response = test_client.post("/chat", json=payload)
    assert response.status_code == 200
    body = response.text
    assert "analyze_change_impact" in body
    assert "PMP-0010" in body
    assert "Blast Radius" in body or "Affected Assemblies" in body


def test_chat_endpoint_draft_safety_gate(test_client: TestClient):
    """Verify AI assistant mutation safety: drafts change with confirm=False."""
    initial_res = test_client.get("/changes?page=1&page_size=1")
    initial_count = initial_res.json()["total"]

    payload = {
        "message": "Draft an ECR for PMP-0290 due to vibration failure in bearing housing",
        "history": [],
    }
    response = test_client.post("/chat", json=payload)
    assert response.status_code == 200
    body = response.text
    assert "draft_change_request" in body
    assert "event: draft_created" in body
    assert "DRAFT-" in body
    assert "SAFETY PROTOCOL ACTIVE" in body or "safety" in body.lower()

    # Verify the database was NOT modified
    after_res = test_client.get("/changes?page=1&page_size=1")
    assert after_res.json()["total"] == initial_count


# =============================================================================
# 9. Digital Thread Endpoint (GET /digital-thread/{number})
# =============================================================================

def test_get_digital_thread_success(test_client: TestClient):
    """Test retrieving complete cross-domain digital thread for PMP-0290."""
    response = test_client.get("/digital-thread/PMP-0290")
    assert response.status_code == 200
    data = response.json()
    assert data["part_number"] == "PMP-0290"
    assert "Cylindrical Roller Bearing" in data["part_name"]
    assert data["stock_summary"] is not None
    assert data["stock_summary"]["total_on_hand"] == 245.0
    assert len(data["open_pos"]) >= 1
    assert any(po["po_number"] == "PO-2025-0812" for po in data["open_pos"])
    assert len(data["defects"]) >= 1
    assert any(d["defect_number"] == "DEF-2025-0042" for d in data["defects"])
    assert len(data["telemetry_events"]) >= 1
    assert any(e["serial_number"] == "SN-APX-2025-001" for e in data["telemetry_events"])
    assert data["impact"] is not None
    assert len(data["timeline"]) >= 4

    # Verify timeline is sorted chronologically
    timestamps = [evt["timestamp"] for evt in data["timeline"]]
    assert timestamps == sorted(timestamps)


def test_get_digital_thread_not_found(test_client: TestClient):
    """Test 404 response for non-existent part in digital thread."""
    response = test_client.get("/digital-thread/PMP-9999")
    assert response.status_code == 404
    data = response.json()
    assert data["error"] == "NotFound"



