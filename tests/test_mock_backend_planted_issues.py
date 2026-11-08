"""Tests verifying MockBackend implementation and detection of all planted issues."""

import pytest
from mock_backend import MockBackend
from seed_data import generate_dataset


@pytest.fixture(scope="module")
def seeded_backend(tmp_path_factory):
    """Fixture providing a seeded MockBackend instance for testing."""
    db_file = str(tmp_path_factory.mktemp("plm") / "test_plm_mock.db")
    generate_dataset(db_path=db_file)
    backend = MockBackend(db_path=db_file)
    yield backend
    backend.close()


# =============================================================================
# Core PLM Operations: Versioning, Recursive BOM & Where-Used
# =============================================================================

def test_get_part_latest_vs_specific_version(seeded_backend: MockBackend):
    # PMP-0001 is seeded with revision B iteration 1
    part_latest = seeded_backend.get_part("PMP-0001")
    assert part_latest is not None
    assert part_latest.version_label == "B.1"

    # Query non-existent part
    assert seeded_backend.get_part("PMP-9999") is None


def test_search_parts(seeded_backend: MockBackend):
    # Search by keyword
    results = seeded_backend.search_parts("ApexFlow", limit=10)
    assert len(results) >= 1
    assert any(r.part_number == "PMP-0001" for r in results)

    # Search with state filter
    released = seeded_backend.search_parts(lifecycle_state="RELEASED", limit=50)
    assert len(released) > 0
    assert all(r.lifecycle_state.value == "RELEASED" for r in released)


def test_recursive_cte_get_bom(seeded_backend: MockBackend):
    # Level 1 BOM (direct children)
    bom_l1 = seeded_backend.get_bom("PMP-0001", levels=1)
    assert len(bom_l1) >= 6
    assert all(link.level == 1 for link in bom_l1)

    # Multi-level BOM (levels = 4)
    bom_l4 = seeded_backend.get_bom("PMP-0001", levels=4)
    assert len(bom_l4) > len(bom_l1)

    levels_found = {link.level for link in bom_l4}
    assert 1 in levels_found
    assert 2 in levels_found
    assert 3 in levels_found
    assert 4 in levels_found


def test_recursive_cte_where_used(seeded_backend: MockBackend):
    # Component PMP-0381 is a Level 5 part used under PMP-0221
    direct_used = seeded_backend.where_used("PMP-0381", recursive=False)
    assert len(direct_used) >= 1
    assert all(r["level"] == 1 for r in direct_used)

    # Recursive where-used should traverse up to root pump assembly
    recursive_used = seeded_backend.where_used("PMP-0381", recursive=True)
    assert len(recursive_used) > len(direct_used)

    parent_numbers = [r["parent_part_number"] for r in recursive_used]
    # Should trace up to Level 0 pump assembly PMP-0001
    assert "PMP-0001" in parent_numbers


# =============================================================================
# Planted Issue 1: 10 Near-Duplicate Parts (5 Duplicate Pairs)
# =============================================================================

def test_detect_planted_issue_1_duplicates(seeded_backend: MockBackend):
    duplicate_groups = seeded_backend.find_duplicates()

    # Must find all 5 duplicate groups
    assert len(duplicate_groups) == 5

    detected_part_numbers = set()
    for group in duplicate_groups:
        assert len(group.parts) == 2, f"Group {group.match_value} should have exactly 2 duplicate parts"
        for p in group.parts:
            detected_part_numbers.add(p.part_number)

    expected_duplicates = {
        "PMP-0041", "PMP-0042",  # M12x45mm 316SS Hex Screw
        "PMP-0088", "PMP-0089",  # Viton O-Ring 75x3.5mm
        "PMP-0145", "PMP-0146",  # Ball Bearing 6309 C3
        "PMP-0210", "PMP-0211",  # Shaft Sleeve Duplex 2205
        "PMP-0335", "PMP-0336",  # Spiral Wound Flange Gasket 4" 300#
    }
    assert detected_part_numbers == expected_duplicates


# =============================================================================
# Planted Issue 2: 8 Obsolete Parts in Released BOMs
# =============================================================================

def test_detect_planted_issue_2_obsolete_in_released(seeded_backend: MockBackend):
    violations = seeded_backend.find_obsolete_in_released()

    assert len(violations) == 8

    expected_obsolete_children = {
        "PMP-0055", "PMP-0092", "PMP-0130", "PMP-0175",
        "PMP-0220", "PMP-0280", "PMP-0315", "PMP-0390"
    }
    found_children = {v.obsolete_child_part_number for v in violations}
    assert found_children == expected_obsolete_children

    # Verify all parents are RELEASED and children are OBSOLETE
    for v in violations:
        assert v.parent_lifecycle_state == "RELEASED"
        assert v.obsolete_child_state == "OBSOLETE"


# =============================================================================
# Planted Issue 3: 12 Buy Parts with No Supplier (AML Gaps)
# =============================================================================

def test_detect_planted_issue_3_no_supplier(seeded_backend: MockBackend):
    unassigned_buy = seeded_backend.find_unassigned_buy_parts()

    assert len(unassigned_buy) == 12

    expected_no_supplier_parts = {
        "PMP-0061", "PMP-0074", "PMP-0112", "PMP-0158",
        "PMP-0199", "PMP-0245", "PMP-0268", "PMP-0305",
        "PMP-0348", "PMP-0382", "PMP-0422", "PMP-0465"
    }
    found_parts = {p.part_number for p in unassigned_buy}
    assert found_parts == expected_no_supplier_parts
    assert all(p.make_buy == "BUY" for p in unassigned_buy)


# =============================================================================
# Planted Issue 4: 5 EBOM vs MBOM Mismatches
# =============================================================================

def test_detect_planted_issue_4_ebom_mbom_mismatches(seeded_backend: MockBackend):
    mismatches = seeded_backend.find_ebom_mbom_mismatches()
    assert len(mismatches) == 5

    # Test compare_boms specifically on the mismatched casing studs (PMP-0001)
    comp = seeded_backend.compare_boms("PMP-0001:EBOM", "PMP-0001:MBOM")
    assert "PMP-0025" in comp.modified_parts

    stud_diff = next(d for d in comp.differences if d.part_number == "PMP-0025")
    assert stud_diff.quantity_a == 16.0  # EBOM
    assert stud_diff.quantity_b == 20.0  # MBOM

    # Test shop balance weight added in MBOM only (PMP-0007)
    comp_rotor = seeded_backend.compare_boms("PMP-0007:EBOM", "PMP-0007:MBOM")
    assert "PMP-0078" in comp_rotor.added_parts

    # Test coupling guard omitted in MBOM (PMP-0010)
    comp_coupling = seeded_backend.compare_boms("PMP-0010:EBOM", "PMP-0010:MBOM")
    assert "PMP-0290" in comp_coupling.removed_parts


# =============================================================================
# Planted Issue 5: 6 Parts with RoHS Non-Compliant Materials
# =============================================================================

def test_detect_planted_issue_5_rohs_materials(seeded_backend: MockBackend):
    rohs_risks = seeded_backend.find_rohs_risks()
    assert len(rohs_risks) == 6

    expected_rohs_parts = {
        "PMP-0018",  # Free-Cutting Brass (Lead > 4.2%)
        "PMP-0082",  # Cadmium Plated Tie-Rod
        "PMP-0164",  # Hexavalent Chromium Passivated Shims
        "PMP-0238",  # Mercury Wetted Tilt Switch
        "PMP-0322",  # Deca-BDE Flame Retardant Packing
        "PMP-0415",  # DEHP Phthalate Cable Sheath
    }
    found_rohs_parts = {r["part_number"] for r in rohs_risks}
    assert found_rohs_parts == expected_rohs_parts

    # Verify analyze_change_impact marks RoHS risk as CRITICAL
    impact = seeded_backend.analyze_change_impact("PMP-0018")
    assert impact.impact_level == "CRITICAL"


# =============================================================================
# Change Impact Analysis & Change Request Drafting
# =============================================================================

def test_analyze_change_impact(seeded_backend: MockBackend):
    # Test change impact on an obsolete part used in a released pump
    impact = seeded_backend.analyze_change_impact("PMP-0055")
    assert impact.target_part_number == "PMP-0055"
    assert impact.target_lifecycle_state == "OBSOLETE"
    assert "PMP-0006" in impact.direct_parents
    assert "PMP-0001" in impact.all_affected_assemblies
    assert impact.impact_level in ("HIGH", "CRITICAL")


def test_draft_change_request(seeded_backend: MockBackend):
    cr = seeded_backend.draft_change_request(
        title="Resolve RoHS Lead Non-Compliance on Drain Plug",
        affected_parts=["PMP-0018"],
        reason="Exceeds 4.0% lead exemption under RoHS Annex III (6c); replace with lead-free brass.",
    )
    assert cr.cr_number.startswith("CR-")
    assert cr.status == "OPEN"
    assert "PMP-0018" in cr.affected_parts

    # Error handling for non-existent part
    with pytest.raises(ValueError, match="does not exist"):
        seeded_backend.draft_change_request(
            title="Invalid Change",
            affected_parts=["PMP-INVALID-PART"],
            reason="Testing validation",
        )

