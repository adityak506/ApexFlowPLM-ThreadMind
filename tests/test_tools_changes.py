"""Tests for Change Management MCP tools covering ECR, ECN, and workflows."""

from plm_mcp.tools.changes import (
    add_change_affected_item,
    create_change_notice,
    create_change_request,
    execute_change_notice,
    get_change_notice,
    get_change_request,
)


def test_get_change_request():
    cr = get_change_request("CR-0001")
    assert not isinstance(cr, dict) or "error" not in cr
    assert cr.cr_number == "CR-0001"


def test_get_change_notice():
    cn = get_change_notice("CN-0001")
    assert not isinstance(cn, dict) or "error" not in cn
    assert cn.cn_number == "CN-0001"


def test_change_request_workflow():
    # Dry run
    dry = create_change_request("Cost reduction motor", "Swap bearing", confirm=False)
    assert dry.success is True
    assert dry.is_dry_run is True

    # Confirmed
    live = create_change_request("Cost reduction motor", "Swap bearing", confirm=True)
    assert live.success is True
    assert live.is_dry_run is False
    cr_num = live.applied_data["cr_number"]

    # Verify retrieval
    cr = get_change_request(cr_num)
    assert cr.cr_number == cr_num


def test_change_notice_workflow():
    # Create notice
    live_cn = create_change_notice("ECN test", "Implementing fix", confirm=True)
    cn_num = live_cn.applied_data["cn_number"]

    # Add affected item
    aff = add_change_affected_item(cn_num, "PART", "DRN-2010", disposition="USE_AS_IS", confirm=True)
    assert aff.success is True
    assert aff.applied_data["item_number"] == "DRN-2010"

    # Execute change notice
    exec_res = execute_change_notice(cn_num, confirm=True)
    assert exec_res.success is True
    assert exec_res.applied_data["state"] == "COMPLETED"

