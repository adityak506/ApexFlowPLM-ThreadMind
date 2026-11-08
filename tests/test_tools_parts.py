"""Tests for Part MCP tools covering safety dry-run and confirmed mutations."""

from plm_mcp.tools.parts import (
    create_part,
    get_part,
    iterate_part,
    revise_part,
    search_parts,
    set_part_lifecycle_state,
)


def test_get_part_success():
    result = get_part("DRN-1000")
    assert not isinstance(result, dict) or "error" not in result
    assert result.master.part_number == "DRN-1000"


def test_get_part_not_found():
    result = get_part("NON-EXISTENT")
    assert isinstance(result, dict)
    assert "error" in result


def test_search_parts():
    results = search_parts("Motor")
    assert len(results) > 0
    assert any("Motor" in r.name for r in results)


def test_create_part_dry_run_and_confirm():
    # 1. Dry Run (default confirm=False)
    dry = create_part("TST-9001", "Dry Run Part", "Draft preview", confirm=False)
    assert dry.success is True
    assert dry.is_dry_run is True
    assert "DRY RUN" in dry.message
    # Check that it was NOT created in DB
    check = get_part("TST-9001")
    assert isinstance(check, dict) and "error" in check

    # 2. Confirmed Write
    live = create_part("TST-9001", "Dry Run Part", "Draft preview", confirm=True)
    assert live.success is True
    assert live.is_dry_run is False
    assert live.applied_data["part_number"] == "TST-9001"
    assert live.applied_data["version_label"] == "A.1"

    # Confirm it exists now
    part = get_part("TST-9001")
    assert part.master.part_number == "TST-9001"


def test_iterate_part_dry_run_and_confirm():
    create_part("TST-9002", "Iteration Part", confirm=True)

    # Dry run
    dry = iterate_part("TST-9002", "Dry run iteration", confirm=False)
    assert dry.success is True
    assert dry.is_dry_run is True
    assert dry.preview_data["next_version"] == "A.2"

    # Confirmed
    live = iterate_part("TST-9002", "Confirmed iteration", confirm=True)
    assert live.success is True
    assert live.is_dry_run is False
    assert live.applied_data["version_label"] == "A.2"


def test_revise_part_dry_run_and_confirm():
    # DRN-3000 is RELEASED in seed data
    dry = revise_part("DRN-3000", confirm=False)
    assert dry.success is True
    assert dry.is_dry_run is True
    assert "DRY RUN" in dry.message

    live = revise_part("DRN-3000", confirm=True)
    assert live.success is True
    assert live.is_dry_run is False
    assert live.applied_data["version_label"] == "C.1"
    assert live.applied_data["lifecycle_state"] == "IN_WORK"


def test_set_part_lifecycle_state():
    create_part("TST-9003", "Lifecycle Part", confirm=True)

    # Dry run
    dry = set_part_lifecycle_state("TST-9003", "UNDER_REVIEW", confirm=False)
    assert dry.success is True
    assert dry.is_dry_run is True

    # Confirmed promotion
    live = set_part_lifecycle_state("TST-9003", "UNDER_REVIEW", confirm=True)
    assert live.success is True
    assert live.applied_data["lifecycle_state"] == "UNDER_REVIEW"

    # Confirmed release
    live_rel = set_part_lifecycle_state("TST-9003", "RELEASED", confirm=True)
    assert live_rel.success is True
    assert live_rel.applied_data["lifecycle_state"] == "RELEASED"

