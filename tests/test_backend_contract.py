"""Contract tests verifying that MockBackend and WindchillBackend satisfy the same interface.

Uses pytest parameterization to run the identical test suite against:
1. MockBackend (SQLite local database)
2. WindchillBackend (PTC Windchill REST / OData with requests)
"""

import pytest
from mock_backend import MockBackend
from plm_interface import BomLink, LifecycleState, Part, PLMBackend
from seed_data import generate_dataset
from windchill_backend import WindchillBackend


class MockODataResponse:
    """Mock HTTP response returned by mock Windchill requests.Session."""

    def __init__(self, status_code: int, data: dict):
        self.status_code = status_code
        self._data = data

    def json(self) -> dict:
        return self._data

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP Error {self.status_code}")


class MockWindchillSession:
    """Simulates Windchill OData server handling $filter, $expand, $top, and $skip."""

    def __init__(self):
        self.headers = {}
        self.auth = None

        # Simulated Windchill OData catalog
        self.parts_db = [
            {
                "Number": "PMP-0001",
                "Name": "ApexFlow 1000 End-Suction Centrifugal Pump",
                "VersionID": "B.1",
                "State": {"Value": "RELEASED"},
                "Description": "Flagship industrial centrifugal slurry pump",
                "Source": {"Value": "make"},
                "Material": "Cast Steel ASTM A216 WCB",
                "CreatedOn": "2025-01-15T08:30:00Z",
                "PartStructure": [
                    {
                        "Quantity": {"Value": 2.0, "Unit": "ea"},
                        "FindNumber": 10,
                        "Part": {
                            "Number": "PMP-0006",
                            "Name": "Seal Flush Pipe Subassembly 40mm",
                            "VersionID": "A.1",
                            "State": {"Value": "RELEASED"},
                        },
                    },
                    {
                        "Quantity": {"Value": 1.0, "Unit": "ea"},
                        "FindNumber": 20,
                        "Part": {
                            "Number": "PMP-0010",
                            "Name": "Shaft Subassembly 25mm",
                            "VersionID": "A.1",
                            "State": {"Value": "RELEASED"},
                        },
                    },
                ],
            },
            {
                "Number": "PMP-0006",
                "Name": "Seal Flush Pipe Subassembly 40mm",
                "VersionID": "A.1",
                "State": {"Value": "RELEASED"},
                "Description": "Auxiliary seal flush piping",
                "Source": {"Value": "make"},
                "Material": "316L Stainless Steel",
                "CreatedOn": "2025-01-16T09:00:00Z",
                "PartStructure": [],
            },
            {
                "Number": "PMP-0010",
                "Name": "Shaft Subassembly 25mm",
                "VersionID": "A.1",
                "State": {"Value": "RELEASED"},
                "Description": "Precision ground pump drive shaft",
                "Source": {"Value": "make"},
                "Material": "Cast Steel ASTM A216 WCB",
                "CreatedOn": "2025-01-17T10:00:00Z",
                "PartStructure": [
                    {
                        "Quantity": {"Value": 1.0, "Unit": "ea"},
                        "FindNumber": 10,
                        "Part": {
                            "Number": "PMP-0290",
                            "Name": "Cylindrical Roller Bearing 25mm",
                            "VersionID": "C.1",
                            "State": {"Value": "RELEASED"},
                        },
                    }
                ],
            },
            {
                "Number": "PMP-0050",
                "Name": "Internal Retaining Ring 250mm",
                "VersionID": "A.1",
                "State": {"Value": "UNDER_REVIEW"},
                "Description": "Internal carbon steel retaining snap ring",
                "Source": {"Value": "make"},
                "Material": "Tungsten Carbide (WC)",
                "CreatedOn": "2025-01-18T11:00:00Z",
                "PartStructure": [],
            },
            {
                "Number": "PMP-0290",
                "Name": "Cylindrical Roller Bearing 25mm",
                "VersionID": "C.1",
                "State": {"Value": "RELEASED"},
                "Description": "Precision cylindrical roller bearing",
                "Source": {"Value": "buy"},
                "Material": "Silicon Carbide (SiC)",
                "CreatedOn": "2025-01-19T12:00:00Z",
                "PartStructure": [],
            },
        ]

    def get(self, url: str, params: dict | None = None, timeout: float = 30.0) -> MockODataResponse:
        params = params or {}
        results = list(self.parts_db)

        # 1. Process $filter
        filter_expr = params.get("$filter", "")
        if "Number eq" in filter_expr:
            # Exact match: Number eq '...'
            import re
            m = re.search(r"Number eq '([^']+)'", filter_expr)
            if m:
                target_num = m.group(1)
                results = [p for p in results if p["Number"] == target_num]

        if "contains(" in filter_expr:
            # Substring match: contains(Number, '...') or contains(Name, '...')
            import re
            m = re.search(r"contains\(\w+, '([^']+)'\)", filter_expr)
            if m:
                q = m.group(1).lower()
                results = [
                    p for p in results
                    if q in p["Number"].lower() or q in p["Name"].lower() or q in p["Description"].lower()
                ]

        if "State/Value eq" in filter_expr:
            import re
            m = re.search(r"State/Value eq '([^']+)'", filter_expr)
            if m:
                target_state = m.group(1).upper()
                results = [p for p in results if p["State"]["Value"].upper() == target_state]

        # 2. Process $skip and $top
        skip = int(params.get("$skip", 0))
        top = int(params.get("$top", len(results)))
        paged_results = results[skip : skip + top]

        # 3. Process $expand
        expand = params.get("$expand", "")
        formatted_items = []
        for p in paged_results:
            item = dict(p)
            if "PartStructure" not in expand:
                item.pop("PartStructure", None)
            formatted_items.append(item)

        return MockODataResponse(status_code=200, data={"value": formatted_items})


@pytest.fixture(params=["mock", "windchill"])
def plm_backend(request, tmp_path) -> PLMBackend:
    """Fixture providing parameterized backend instances (Mock and Windchill)."""
    backend_type = request.param

    if backend_type == "mock":
        db_path = str(tmp_path / "contract_test_mock.db")
        generate_dataset(db_path=db_path)
        backend = MockBackend(db_path=db_path)
        yield backend
        backend.close()

    elif backend_type == "windchill":
        mock_session = MockWindchillSession()
        backend = WindchillBackend(
            base_url="https://windchill.internal",
            username="wcadmin",
            password="mock_password",
            session=mock_session,
        )
        yield backend


# =============================================================================
# PLMBackend Contract Tests
# =============================================================================

def test_contract_implements_interface(plm_backend):
    """Verify that both backends adhere to the abstract PLMBackend contract."""
    assert isinstance(plm_backend, PLMBackend)


def test_contract_search_parts_all(plm_backend):
    """Verify that search_parts returns a valid list of normalized Part objects."""
    parts = plm_backend.search_parts(limit=10)
    assert isinstance(parts, list)
    assert len(parts) > 0
    for p in parts:
        assert isinstance(p, Part)
        assert p.part_number
        assert p.name
        assert p.version_label
        assert isinstance(p.lifecycle_state, LifecycleState)


def test_contract_search_parts_with_query(plm_backend):
    """Verify text search filtering across both backends."""
    results = plm_backend.search_parts(query="PMP-0001", limit=10)
    assert len(results) >= 1
    target = next((p for p in results if p.part_number == "PMP-0001"), None)
    assert target is not None
    assert "ApexFlow" in target.name
    assert target.lifecycle_state == LifecycleState.RELEASED


def test_contract_search_parts_lifecycle_filter(plm_backend):
    """Verify lifecycle state filtering across both backends."""
    released_parts = plm_backend.search_parts(lifecycle_state="RELEASED", limit=15)
    assert len(released_parts) > 0
    for p in released_parts:
        assert p.lifecycle_state == LifecycleState.RELEASED


def test_contract_search_parts_pagination(plm_backend):
    """Verify that limit pagination constraint is respected."""
    parts = plm_backend.search_parts(limit=2)
    assert len(parts) <= 2


def test_contract_get_part_found(plm_backend):
    """Verify retrieving an existing part by number."""
    part = plm_backend.get_part("PMP-0001")
    assert part is not None
    assert isinstance(part, Part)
    assert part.part_number == "PMP-0001"
    assert "ApexFlow" in part.name


def test_contract_get_part_not_found(plm_backend):
    """Verify retrieving a non-existent part returns None."""
    missing = plm_backend.get_part("PMP-NON-EXISTENT-9999")
    assert missing is None


def test_contract_get_bom_single_level(plm_backend):
    """Verify single-level BOM retrieval adheres to BomLink contract."""
    links = plm_backend.get_bom("PMP-0001", levels=1)
    assert isinstance(links, list)
    assert len(links) >= 2
    for link in links:
        assert isinstance(link, BomLink)
        assert link.parent_part_number == "PMP-0001"
        assert link.child_part_number
        assert link.quantity > 0
        assert link.level == 1


def test_contract_get_bom_multi_level(plm_backend):
    """Verify multi-level BOM explosion traverses down hierarchy."""
    links = plm_backend.get_bom("PMP-0001", levels=2)
    assert isinstance(links, list)
    assert len(links) >= 3

    child_numbers = [link.child_part_number for link in links]
    # In both backends, PMP-0001 -> PMP-0010 -> PMP-0290
    assert "PMP-0010" in child_numbers
    assert "PMP-0290" in child_numbers

    levels_found = {link.level for link in links}
    assert 1 in levels_found
    assert 2 in levels_found

