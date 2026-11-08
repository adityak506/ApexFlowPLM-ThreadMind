"""Tests for Pydantic models, schemas, and Windchill versioning rules."""

from plm_mcp.models import (
    DocType,
    LifecycleState,
    PartDetail,
    PartMaster,
    PartVersion,
    SourcingStatus,
)


def test_part_version_formatting():
    assert PartVersion.format_version("A", 1) == "A.1"
    assert PartVersion.format_version("B", 3) == "B.3"
    assert PartVersion.format_version("AA", 2) == "AA.2"


def test_part_detail_model_validation():
    master = PartMaster(id="m-1", part_number="PRT-001", name="Test Part")
    version = PartVersion(
        id="v-1",
        master_id="m-1",
        part_number="PRT-001",
        name="Test Part",
        revision="A",
        iteration=1,
        version_label="A.1",
        lifecycle_state=LifecycleState.IN_WORK,
    )
    detail = PartDetail(
        master=master,
        version=version,
        bom_components_count=2,
        documents_count=1,
        aml_entries_count=1,
    )
    assert detail.master.part_number == "PRT-001"
    assert detail.version.version_label == "A.1"
    assert detail.version.lifecycle_state == LifecycleState.IN_WORK
    assert detail.bom_components_count == 2


def test_enums():
    assert LifecycleState.IN_WORK.value == "IN_WORK"
    assert LifecycleState.RELEASED.value == "RELEASED"
    assert DocType.CAD_DRAWING.value == "CAD_DRAWING"
    assert SourcingStatus.PREFERRED.value == "PREFERRED"

