"""Tests for plm_interface.py and schema.sql."""

import sqlite3
import pytest
from plm_interface import (
    BomComparisonItem,
    BomComparisonResult,
    BomLink,
    ChangeCategory,
    ChangeImpactAnalysis,
    ChangePriority,
    ChangeRequest,
    Document,
    DocType,
    DuplicateGroup,
    LifecycleState,
    ObsoleteUsageItem,
    Part,
    PLMBackend,
    SourcingStatus,
    Supplier,
)


def test_plm_interface_models():
    # Part
    part = Part(
        part_number="PRT-100",
        name="Main Chassis",
        revision="A",
        iteration=1,
        version_label="A.1",
        lifecycle_state=LifecycleState.IN_WORK,
        description="Structural aluminum chassis",
    )
    assert part.part_number == "PRT-100"
    assert part.version_label == "A.1"

    # BomLink
    bom_link = BomLink(
        parent_part_number="PRT-100",
        child_part_number="SCR-010",
        child_name="M3 Screw",
        quantity=8.0,
        unit="ea",
        find_number=10,
        ref_designators="F1-F8",
        level=1,
    )
    assert bom_link.quantity == 8.0
    assert bom_link.find_number == 10

    # Document
    doc = Document(
        doc_number="DOC-001",
        name="Chassis Stress Analysis",
        doc_type=DocType.TEST_REPORT,
        file_name="stress_analysis.pdf",
        linked_parts=["PRT-100"],
    )
    assert doc.doc_number == "DOC-001"
    assert "PRT-100" in doc.linked_parts

    # ChangeRequest
    cr = ChangeRequest(
        cr_number="CR-0001",
        title="Reduce chassis mass",
        reason="Exceeds target mass limit by 5%",
        category=ChangeCategory.COST_REDUCTION,
        priority=ChangePriority.HIGH,
        affected_parts=["PRT-100"],
    )
    assert cr.cr_number == "CR-0001"
    assert cr.status == "OPEN"

    # Supplier
    sup = Supplier(
        name="Aerospace Metals Corp",
        cage_code="9AM01",
        country="USA",
        manufacturer_parts=["AMC-AL-6061"],
        sourcing_status=SourcingStatus.PREFERRED,
    )
    assert sup.name == "Aerospace Metals Corp"
    assert sup.sourcing_status == SourcingStatus.PREFERRED


def test_plm_interface_analytics_models():
    # BomComparisonResult
    diff = BomComparisonItem(
        part_number="SCR-010",
        name="M3 Screw",
        change_type="QUANTITY_CHANGED",
        quantity_a=8.0,
        quantity_b=12.0,
    )
    res = BomComparisonResult(
        assembly_a="ASM-01:A.1",
        assembly_b="ASM-01:B.1",
        differences=[diff],
        modified_parts=["SCR-010"],
    )
    assert len(res.differences) == 1
    assert res.modified_parts == ["SCR-010"]

    # ObsoleteUsageItem
    obs = ObsoleteUsageItem(
        parent_part_number="ASM-01",
        parent_name="Top Assembly",
        parent_version="A.2",
        parent_lifecycle_state="RELEASED",
        obsolete_child_part_number="CMP-09",
        obsolete_child_name="Legacy Diode",
        obsolete_child_version="A.1",
        obsolete_child_state="OBSOLETE",
        quantity=2.0,
        unit="ea",
    )
    assert obs.parent_lifecycle_state == "RELEASED"
    assert obs.obsolete_child_state == "OBSOLETE"

    # ChangeImpactAnalysis
    impact = ChangeImpactAnalysis(
        target_part_number="CMP-09",
        target_part_name="Legacy Diode",
        target_lifecycle_state="OBSOLETE",
        direct_parents=["ASM-01"],
        all_affected_assemblies=["ASM-01", "TOP-SYSTEM"],
        associated_documents=["DOC-001"],
        active_change_requests=["CR-0001"],
        approved_suppliers=["Aerospace Metals Corp"],
        impact_level="HIGH",
    )
    assert impact.impact_level == "HIGH"
    assert len(impact.all_affected_assemblies) == 2


def test_plm_backend_abstract_methods():
    # PLMBackend cannot be instantiated without implementations
    with pytest.raises(TypeError):
        PLMBackend()

    # Verify all 9 requested methods exist as abstract methods
    expected_methods = {
        "search_parts",
        "get_part",
        "get_bom",
        "where_used",
        "compare_boms",
        "find_duplicates",
        "find_obsolete_in_released",
        "analyze_change_impact",
        "draft_change_request",
    }
    abstracts = PLMBackend.__abstractmethods__
    for method in expected_methods:
        assert method in abstracts, f"Missing abstract method: {method}"


def test_schema_sql_execution():
    conn = sqlite3.connect(":memory:")
    with open("schema.sql", "r", encoding="utf-8") as f:
        ddl = f.read()

    conn.executescript(ddl)

    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    expected_tables = {
        "part_masters",
        "part_versions",
        "bom_links",
        "document_masters",
        "document_versions",
        "part_doc_links",
        "change_requests",
        "change_notices",
        "change_affected_items",
        "change_resulting_items",
        "manufacturers",
        "manufacturer_parts",
        "aml_links",
    }

    for tbl in expected_tables:
        assert tbl in tables, f"Expected table '{tbl}' was not created by schema.sql"

