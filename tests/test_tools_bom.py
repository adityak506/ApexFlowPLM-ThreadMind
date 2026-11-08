"""Tests for BOM MCP tools covering hierarchy, explosion, and usage link modifications."""

from plm_mcp.tools.bom import (
    add_bom_component,
    get_part_bom,
    get_where_used,
    remove_bom_component,
)
from plm_mcp.tools.parts import create_part


def test_get_part_bom():
    bom = get_part_bom("DRN-1000", levels=2)
    assert not isinstance(bom, dict) or "error" not in bom
    assert bom.part_number == "DRN-1000"
    assert len(bom.children) > 0


def test_get_where_used():
    where_used = get_where_used("DRN-2010")
    assert len(where_used) > 0
    assert any(item.parent_part_number == "DRN-2000" for item in where_used)


def test_add_and_remove_bom_component():
    create_part("ASM-PARENT", "Parent Assembly", confirm=True)
    create_part("CMP-CHILD", "Child Component", confirm=True)

    # Dry-run add
    dry_add = add_bom_component("ASM-PARENT", "CMP-CHILD", quantity=2.0, confirm=False)
    assert dry_add.success is True
    assert dry_add.is_dry_run is True

    # Confirmed add
    live_add = add_bom_component("ASM-PARENT", "CMP-CHILD", quantity=2.0, confirm=True)
    assert live_add.success is True
    assert live_add.is_dry_run is False

    # Check BOM has component
    bom = get_part_bom("ASM-PARENT")
    assert len(bom.children) == 1
    assert bom.children[0].part_number == "CMP-CHILD"
    assert bom.children[0].quantity == 2.0

    # Dry-run remove
    dry_rm = remove_bom_component("ASM-PARENT", "CMP-CHILD", confirm=False)
    assert dry_rm.success is True
    assert dry_rm.is_dry_run is True

    # Confirmed remove
    live_rm = remove_bom_component("ASM-PARENT", "CMP-CHILD", confirm=True)
    assert live_rm.success is True
    assert live_rm.is_dry_run is False

    # Check BOM is empty
    bom_after = get_part_bom("ASM-PARENT")
    assert len(bom_after.children) == 0

