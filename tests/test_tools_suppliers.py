"""Tests for Supplier & AML MCP tools covering manufacturer catalog and sourcing links."""

from plm_mcp.tools.suppliers import (
    add_manufacturer,
    add_manufacturer_part,
    get_part_aml,
    search_manufacturers,
    set_sourcing_link,
)


def test_search_manufacturers():
    results = search_manufacturers("T-Motor")
    assert len(results) > 0
    assert results[0].name == "T-Motor Tech Co."


def test_get_part_aml():
    aml = get_part_aml("DRN-3010")
    assert len(aml) > 0
    assert aml[0].sourcing_status.value == "PREFERRED"


def test_supplier_registration_and_sourcing():
    # Dry run add manufacturer
    dry_m = add_manufacturer("Samsung SDI", country="South Korea", confirm=False)
    assert dry_m.success is True
    assert dry_m.is_dry_run is True

    # Confirmed add manufacturer
    live_m = add_manufacturer("Samsung SDI", country="South Korea", confirm=True)
    assert live_m.success is True
    assert live_m.is_dry_run is False

    # Dry run add part
    dry_p = add_manufacturer_part("Samsung SDI", "INR21700-40T", confirm=False)
    assert dry_p.success is True
    assert dry_p.is_dry_run is True

    # Confirmed add part
    live_p = add_manufacturer_part("Samsung SDI", "INR21700-40T", confirm=True)
    assert live_p.success is True

    # Set sourcing link
    live_link = set_sourcing_link(
        part_number="DRN-3000",
        mfr_name="Samsung SDI",
        mfr_part_number="INR21700-40T",
        status="PREFERRED",
        preference_rank=1,
        confirm=True,
    )
    assert live_link.success is True
    assert live_link.applied_data["sourcing_status"] == "PREFERRED"

