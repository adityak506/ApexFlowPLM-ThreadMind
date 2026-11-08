"""Tests verifying the deterministic seed_data.py generator and planted issues."""

import sqlite3
import pytest
from seed_data import generate_dataset


@pytest.fixture
def test_db_path(tmp_path):
    return str(tmp_path / "test_plm_dataset.db")


def test_seed_data_generation_summary(test_db_path):
    summary = generate_dataset(db_path=test_db_path)
    assert summary["status"] == "success"
    assert summary["parts_count"] == 500
    assert summary["suppliers_count"] == 30
    assert summary["documents_count"] == 20
    assert summary["change_requests_count"] == 15
    assert summary["bom_links_count"] > 900


def test_planted_issue_1_duplicates(test_db_path):
    generate_dataset(db_path=test_db_path)
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Check 5 duplicate pairs (10 parts)
    duplicate_pairs = [
        ("PMP-0041", "PMP-0042"),
        ("PMP-0088", "PMP-0089"),
        ("PMP-0145", "PMP-0146"),
        ("PMP-0210", "PMP-0211"),
        ("PMP-0335", "PMP-0336"),
    ]

    for p1, p2 in duplicate_pairs:
        cursor.execute("SELECT m.part_number, v.material, v.make_buy FROM part_masters m JOIN part_versions v ON m.id = v.master_id WHERE m.part_number IN (?, ?)", (p1, p2))
        rows = cursor.fetchall()
        assert len(rows) == 2, f"Expected both {p1} and {p2} to exist"
        # Materials and make/buy must match
        assert rows[0]["material"] == rows[1]["material"]
        assert rows[0]["make_buy"] == rows[1]["make_buy"]


def test_planted_issue_2_obsolete_in_released(test_db_path):
    generate_dataset(db_path=test_db_path)
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Query released parents using obsolete children
    cursor.execute(
        """
        SELECT DISTINCT p_parent.part_number AS parent, p_child.part_number AS child
        FROM bom_links b
        JOIN part_versions v_parent ON b.parent_version_id = v_parent.id
        JOIN part_masters p_parent ON v_parent.master_id = p_parent.id
        JOIN part_masters p_child ON b.child_master_id = p_child.id
        JOIN part_versions v_child ON v_child.master_id = p_child.id
        WHERE v_parent.lifecycle_state = 'RELEASED'
          AND v_child.lifecycle_state = 'OBSOLETE'
          AND b.notes LIKE '%PLANTED_OBSOLETE%'
        """
    )
    violations = cursor.fetchall()
    assert len(violations) == 8, f"Expected 8 obsolete part violations, found {len(violations)}"


def test_planted_issue_3_no_supplier(test_db_path):
    generate_dataset(db_path=test_db_path)
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.part_number, v.make_buy
        FROM part_masters m
        JOIN part_versions v ON m.id = v.master_id
        WHERE v.make_buy = 'BUY'
          AND m.id NOT IN (SELECT part_master_id FROM aml_links)
        """
    )
    unassigned = cursor.fetchall()
    assert len(unassigned) == 12, f"Expected 12 unassigned buy parts, found {len(unassigned)}"


def test_planted_issue_4_ebom_mbom_mismatches(test_db_path):
    generate_dataset(db_path=test_db_path)
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT COUNT(DISTINCT notes) as mismatch_count
        FROM bom_links
        WHERE notes LIKE '%PLANTED_MISMATCH%'
        """
    )
    # 5 planted mismatch notes groups
    row = cursor.fetchone()
    assert row["mismatch_count"] >= 5


def test_planted_issue_5_rohs_materials(test_db_path):
    generate_dataset(db_path=test_db_path)
    conn = sqlite3.connect(test_db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT m.part_number, v.material
        FROM part_masters m
        JOIN part_versions v ON m.id = v.master_id
        WHERE v.material LIKE '%Lead Pb%'
           OR v.material LIKE '%Cadmium%'
           OR v.material LIKE '%Hexavalent Chromium%'
           OR v.material LIKE '%Mercury%'
           OR v.material LIKE '%Deca-BDE%'
           OR v.material LIKE '%DEHP%'
        """
    )
    non_compliant = cursor.fetchall()
    assert len(non_compliant) == 6, f"Expected 6 RoHS non-compliant parts, found {len(non_compliant)}"


def test_bom_depth_hierarchy(test_db_path):
    generate_dataset(db_path=test_db_path)
    conn = sqlite3.connect(test_db_path)
    cursor = conn.cursor()

    # Verify BOM has at least 4 to 5 levels deep
    # Traverse from PMP-0001 (ApexFlow)
    cursor.execute("SELECT id FROM part_masters WHERE part_number = 'PMP-0001'")
    root_id = cursor.fetchone()[0]

    cursor.execute("SELECT id FROM part_versions WHERE master_id = ?", (root_id,))
    v_root = cursor.fetchone()[0]

    # Level 1
    cursor.execute("SELECT child_master_id FROM bom_links WHERE parent_version_id = ? AND bom_type = 'EBOM'", (v_root,))
    l1_masters = [r[0] for r in cursor.fetchall()]
    assert len(l1_masters) >= 5, "Expected at least 5 Level 1 subassemblies"

    # Level 2
    cursor.execute("SELECT child_master_id FROM bom_links WHERE parent_version_id IN (SELECT id FROM part_versions WHERE master_id IN (%s)) AND bom_type = 'EBOM'" % ",".join("?" for _ in l1_masters), l1_masters)
    l2_masters = [r[0] for r in cursor.fetchall()]
    assert len(l2_masters) >= 10, "Expected at least 10 Level 2 subassemblies"

    # Level 3
    cursor.execute("SELECT child_master_id FROM bom_links WHERE parent_version_id IN (SELECT id FROM part_versions WHERE master_id IN (%s)) AND bom_type = 'EBOM'" % ",".join("?" for _ in l2_masters), l2_masters)
    l3_masters = [r[0] for r in cursor.fetchall()]
    assert len(l3_masters) >= 15, "Expected at least 15 Level 3 subassemblies"

    # Level 4
    cursor.execute("SELECT child_master_id FROM bom_links WHERE parent_version_id IN (SELECT id FROM part_versions WHERE master_id IN (%s)) AND bom_type = 'EBOM'" % ",".join("?" for _ in l3_masters), l3_masters)
    l4_masters = [r[0] for r in cursor.fetchall()]
    assert len(l4_masters) >= 15, "Expected at least 15 Level 4 component parts"

    # Level 5
    cursor.execute("SELECT child_master_id FROM bom_links WHERE parent_version_id IN (SELECT id FROM part_versions WHERE master_id IN (%s)) AND bom_type = 'EBOM'" % ",".join("?" for _ in l4_masters), l4_masters)
    l5_masters = [r[0] for r in cursor.fetchall()]
    assert len(l5_masters) >= 10, "Expected at least 10 Level 5 hardware parts"

