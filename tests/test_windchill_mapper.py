"""Tests for windchill_mapper.py mapping functions."""

from datetime import datetime
from plm_interface import LifecycleState
from windchill_mapper import (
    map_windchill_bom_link_to_normalized,
    map_windchill_bom_structure_to_normalized,
    map_windchill_make_buy,
    map_windchill_part_to_normalized,
    map_windchill_parts_to_normalized,
    map_windchill_state,
    map_windchill_version,
)


def test_map_windchill_state():
    assert map_windchill_state("RELEASED") == LifecycleState.RELEASED
    assert map_windchill_state({"Value": "RELEASED", "Display": "Released"}) == LifecycleState.RELEASED
    assert map_windchill_state("IN_WORK") == LifecycleState.IN_WORK
    assert map_windchill_state("INWORK") == LifecycleState.IN_WORK
    assert map_windchill_state("UNDER_REVIEW") == LifecycleState.UNDER_REVIEW
    assert map_windchill_state("OBSOLETE") == LifecycleState.OBSOLETE
    assert map_windchill_state(None) == LifecycleState.IN_WORK


def test_map_windchill_version():
    rev, it, label = map_windchill_version({"VersionID": "B.2"})
    assert rev == "B"
    assert it == 2
    assert label == "B.2"

    rev, it, label = map_windchill_version({"Version": "C", "Iteration": 3})
    assert rev == "C"
    assert it == 3
    assert label == "C.3"


def test_map_windchill_make_buy():
    assert map_windchill_make_buy("buy") == "BUY"
    assert map_windchill_make_buy("MAKE") == "MAKE"
    assert map_windchill_make_buy({"Value": "buy"}) == "BUY"
    assert map_windchill_make_buy(None) == "MAKE"


def test_map_windchill_part():
    raw_odata_part = {
        "Number": "PMP-0001",
        "Name": "ApexFlow Centrifugal Pump",
        "VersionID": "B.1",
        "State": {"Value": "RELEASED"},
        "Description": "Flagship slurry pump",
        "Source": {"Value": "make"},
        "Material": "Cast Steel",
        "CreatedOn": "2025-01-15T08:30:00Z",
    }
    part = map_windchill_part_to_normalized(raw_odata_part)
    assert part.part_number == "PMP-0001"
    assert part.name == "ApexFlow Centrifugal Pump"
    assert part.revision == "B"
    assert part.iteration == 1
    assert part.version_label == "B.1"
    assert part.lifecycle_state == LifecycleState.RELEASED
    assert part.make_buy == "MAKE"
    assert part.material == "Cast Steel"


def test_map_windchill_bom_structure():
    raw_structure = {
        "value": [
            {
                "Quantity": {"Value": 2.0, "Unit": "ea"},
                "FindNumber": 10,
                "ReferenceDesignator": "A1",
                "Part": {
                    "Number": "PMP-0006",
                    "Name": "Seal Flush Pipe",
                    "VersionID": "A.1",
                },
            },
            {
                "Quantity": 1.0,
                "FindNumber": 20,
                "Part": {
                    "Number": "PMP-0010",
                    "Name": "Shaft Subassembly",
                    "VersionID": "A.1",
                },
            },
        ]
    }

    links = map_windchill_bom_structure_to_normalized("PMP-0001", raw_structure, level=1)
    assert len(links) == 2
    assert links[0].parent_part_number == "PMP-0001"
    assert links[0].child_part_number == "PMP-0006"
    assert links[0].quantity == 2.0
    assert links[0].unit == "ea"
    assert links[0].find_number == 10
    assert links[0].ref_designators == "A1"

    assert links[1].child_part_number == "PMP-0010"
    assert links[1].quantity == 1.0

