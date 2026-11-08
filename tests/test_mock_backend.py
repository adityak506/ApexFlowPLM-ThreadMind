"""Unit tests for MockBackend SQLite implementation."""

import pytest
from plm_mcp.backend.mock.backend import MockBackend
from plm_mcp.models import (
    DocType,
    ItemDisposition,
    LifecycleState,
    PartDocLinkType,
    SourcingStatus,
)


def test_part_crud_and_versioning(setup_test_backend: MockBackend):
    backend = setup_test_backend

    # Create part
    pv = backend.create_part("TEST-001", "Test Widget", "Initial draft")
    assert pv.part_number == "TEST-001"
    assert pv.version_label == "A.1"
    assert pv.lifecycle_state == LifecycleState.IN_WORK

    # Iterate while In Work
    it2 = backend.iterate_part("TEST-001", "Second iteration")
    assert it2.version_label == "A.2"
    assert it2.lifecycle_state == LifecycleState.IN_WORK

    # Promote lifecycle
    p_ur = backend.set_part_lifecycle_state("TEST-001", LifecycleState.UNDER_REVIEW)
    assert p_ur.lifecycle_state == LifecycleState.UNDER_REVIEW

    p_rel = backend.set_part_lifecycle_state("TEST-001", LifecycleState.RELEASED)
    assert p_rel.lifecycle_state == LifecycleState.RELEASED

    # Cannot iterate a released part
    with pytest.raises(ValueError, match="Only IN_WORK parts can be iterated"):
        backend.iterate_part("TEST-001")

    # Revise released part -> B.1 In Work
    rev_b = backend.revise_part("TEST-001", "Revision B redesign")
    assert rev_b.version_label == "B.1"
    assert rev_b.lifecycle_state == LifecycleState.IN_WORK


def test_bom_tree_and_where_used(setup_test_backend: MockBackend):
    backend = setup_test_backend

    # Drone top-level BOM (DRN-1000)
    bom_root = backend.get_part_bom("DRN-1000", levels=2)
    assert bom_root is not None
    assert bom_root.part_number == "DRN-1000"
    assert len(bom_root.children) >= 3

    # Where-used analysis on propeller (DRN-3030)
    where_used = backend.get_where_used("DRN-3030")
    assert len(where_used) > 0
    parent_numbers = [item.parent_part_number for item in where_used]
    assert "DRN-3000" in parent_numbers


def test_document_and_part_linking(setup_test_backend: MockBackend):
    backend = setup_test_backend

    doc = backend.create_document(
        doc_number="DOC-TEST-01",
        name="Test Manual",
        doc_type=DocType.USER_MANUAL,
        file_name="manual.pdf",
    )
    assert doc.doc_number == "DOC-TEST-01"
    assert doc.version_label == "A.1"

    link = backend.link_document_to_part(
        part_number="DRN-1000",
        doc_number="DOC-TEST-01",
        link_type=PartDocLinkType.REFERENCES,
    )
    assert link.part_number == "DRN-1000"
    assert link.doc_number == "DOC-TEST-01"


def test_change_management_workflow(setup_test_backend: MockBackend):
    backend = setup_test_backend

    cn = backend.create_change_notice(
        title="Quick test notice",
        description="Testing notice execution",
    )
    assert cn.cn_number.startswith("CN-")

    aff = backend.add_change_affected_item(
        cn_number=cn.cn_number,
        item_type="PART",
        item_number="DRN-2010",
        disposition=ItemDisposition.USE_AS_IS,
    )
    assert aff.item_number == "DRN-2010"

    completed_cn = backend.execute_change_notice(cn.cn_number)
    assert completed_cn.state.value == "COMPLETED"


def test_supplier_and_aml(setup_test_backend: MockBackend):
    backend = setup_test_backend

    mfr = backend.add_manufacturer("Nordic Semiconductor", country="Norway")
    assert mfr.name == "Nordic Semiconductor"

    aml = backend.set_sourcing_link(
        part_number="DRN-4010",
        mfr_name="Nordic Semiconductor",
        mfr_part_number="nRF52840",
        status=SourcingStatus.PREFERRED,
        preference_rank=1,
    )
    assert aml.mfr_part_number == "nRF52840"

    aml_list = backend.get_part_aml("DRN-4010")
    assert any(item.mfr_part_number == "nRF52840" for item in aml_list)

