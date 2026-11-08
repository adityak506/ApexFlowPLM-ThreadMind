"""Tests verifying security controls, input validation, injection defenses, and audit log sanitization."""

import pytest
from plm_interface import LifecycleState
import server
from validators import (
    redact_sensitive_args,
    sanitize_like_pattern,
    sanitize_text,
    validate_bom_levels,
    validate_lifecycle_state,
    validate_pagination_limit,
    validate_part_number,
    validate_part_numbers,
)
from windchill_backend import WindchillBackend


# =============================================================================
# 1. Input Validation & Boundary Checks
# =============================================================================

def test_validate_part_number_valid():
    assert validate_part_number("PMP-0001") == "PMP-0001"
    assert validate_part_number("DRN-1000:A.1") == "DRN-1000:A.1"
    assert validate_part_number("PMP_0025/REV-B") == "PMP_0025/REV-B"


def test_validate_part_number_injection_rejected():
    with pytest.raises(ValueError, match="Invalid part number"):
        validate_part_number("PMP-0001'; DROP TABLE part_masters; --")

    with pytest.raises(ValueError, match="Invalid part number"):
        validate_part_number("PMP 0001<script>")

    with pytest.raises(ValueError, match="Field cannot be blank"):
        validate_part_number("")


def test_sanitize_text_strips_null_bytes():
    raw = "Bearing housing\x00 failure alert"
    clean = sanitize_text(raw, max_length=100)
    assert "\x00" not in clean
    assert clean == "Bearing housing failure alert"


def test_sanitize_text_enforces_length():
    huge_text = "A" * 6000
    with pytest.raises(ValueError, match="exceeds maximum allowed length"):
        sanitize_text(huge_text, max_length=5000, allow_empty=False)


def test_validate_part_numbers_batch():
    parts = ["PMP-0001", "PMP-0006", "PMP-0001"]  # Contains duplicate
    deduped = validate_part_numbers(parts, max_count=5)
    assert deduped == ["PMP-0001", "PMP-0006"]

    with pytest.raises(ValueError, match="At least one affected part"):
        validate_part_numbers([])

    with pytest.raises(ValueError, match="Exceeded maximum batch limit"):
        validate_part_numbers([f"PMP-{i:04d}" for i in range(100)], max_count=10)


def test_validate_bom_levels_bounds():
    assert validate_bom_levels(1) == 1
    assert validate_bom_levels(5) == 5
    assert validate_bom_levels(10) == 10

    with pytest.raises(ValueError, match="BOM levels must be between"):
        validate_bom_levels(0)

    with pytest.raises(ValueError, match="BOM levels must be between"):
        validate_bom_levels(11)


def test_validate_pagination_limit_bounds():
    assert validate_pagination_limit(20) == 20
    assert validate_pagination_limit(500) == 500

    with pytest.raises(ValueError, match="Limit must be between"):
        validate_pagination_limit(-5)

    with pytest.raises(ValueError, match="Limit must be between"):
        validate_pagination_limit(1000)


def test_validate_lifecycle_state():
    assert validate_lifecycle_state("RELEASED") == "RELEASED"
    assert validate_lifecycle_state("in_work") == "IN_WORK"
    assert validate_lifecycle_state(None) is None

    with pytest.raises(ValueError, match="Invalid lifecycle state"):
        validate_lifecycle_state("HACKED_STATE' OR 1=1 --")


# =============================================================================
# 2. Audit Log Redaction & Credential Protection
# =============================================================================

def test_redact_sensitive_args():
    args = {
        "part_number": "PMP-0001",
        "levels": 2,
        "password": "super_secret_password",
        "api_key": "live_sk_1234567890",
        "nested": {
            "token": "bearer_jwt_token_xyz",
            "confirm": True,
        },
    }
    cleaned = redact_sensitive_args(args)
    assert cleaned["part_number"] == "PMP-0001"
    assert cleaned["levels"] == 2
    assert cleaned["password"] == "[REDACTED]"
    assert cleaned["api_key"] == "[REDACTED]"
    assert cleaned["nested"]["token"] == "[REDACTED]"
    assert cleaned["nested"]["confirm"] is True


# =============================================================================
# 3. SQL & OData Injection Defenses
# =============================================================================

def test_sanitize_like_pattern():
    assert sanitize_like_pattern("100%") == "100\\%"
    assert sanitize_like_pattern("pump_part") == "pump\\_part"
    assert sanitize_like_pattern("normal text") == "normal text"


def test_windchill_odata_injection_defense():
    backend = WindchillBackend()
    # Attempting to inject arbitrary OData expressions via lifecycle_state must fail validation
    with pytest.raises(ValueError, match="Invalid lifecycle state"):
        backend.search_parts(query="test", lifecycle_state="' or 1 eq 1 --")


# =============================================================================
# 4. Write-Action Safety Gate & Server Error Handling
# =============================================================================

def test_server_draft_change_request_input_validation():
    # Title exceeds maximum length
    huge_title = "X" * 300
    res = server.draft_change_request(
        title=huge_title,
        affected_parts=["PMP-0001"],
        reason="Valid reason",
        confirm=False,
    )
    assert res["status"] == "ERROR"
    assert "exceeds maximum allowed length" in res["error"]


def test_server_draft_change_request_empty_parts():
    res = server.draft_change_request(
        title="Valid Title",
        affected_parts=[],
        reason="Valid reason",
        confirm=False,
    )
    assert res["status"] == "ERROR"
    assert "At least one affected part" in res["error"]


def test_server_get_part_invalid_input():
    res = server.get_part(part_number="PMP-0001<script>alert(1)</script>")
    assert isinstance(res, dict)
    assert "error" in res
    assert "Invalid part number" in res["error"]

