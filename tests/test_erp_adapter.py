"""Tests for ERP models and MockERPBackend."""

import pytest
from erp_interface import (
    ERPInventorySummary,
    ERPPurchaseOrder,
    ERPStockItem,
    POStatus,
)
from mock_erp_backend import MockERPBackend


@pytest.fixture
def erp_backend():
    return MockERPBackend(db_path="plm_mock.db")


def test_erp_stock_models():
    item = ERPStockItem(
        part_number="PMP-0290",
        warehouse_code="WH-01",
        warehouse_name="Main WH",
        bin_location="A-01",
        quantity_on_hand=100.0,
        quantity_reserved=20.0,
        quantity_available=80.0,
        unit_cost=150.0,
    )
    assert item.part_number == "PMP-0290"
    assert item.quantity_available == 80.0

    summary = ERPInventorySummary(
        part_number="PMP-0290",
        total_on_hand=100.0,
        total_reserved=20.0,
        total_available=80.0,
        total_valuation=15000.0,
        stock_locations=[item],
    )
    assert summary.total_valuation == 15000.0


def test_erp_get_stock_failing_part(erp_backend):
    stock = erp_backend.get_stock("PMP-0290")
    assert stock.part_number == "PMP-0290"
    assert stock.total_on_hand == 245.0
    assert stock.total_available == 200.0
    assert stock.total_valuation == 34912.50
    assert len(stock.stock_locations) == 2


def test_erp_get_stock_empty(erp_backend):
    stock = erp_backend.get_stock("NON_EXISTENT_PART")
    assert stock.total_on_hand == 0.0
    assert stock.total_available == 0.0
    assert len(stock.stock_locations) == 0


def test_erp_get_open_pos(erp_backend):
    pos = erp_backend.get_open_pos("PMP-0290")
    assert len(pos) >= 2
    po_numbers = [po.po_number for po in pos]
    assert "PO-2025-0812" in po_numbers
    assert "PO-2025-0955" in po_numbers

    # Verify status
    in_transit_po = next(p for p in pos if p.po_number == "PO-2025-0812")
    assert in_transit_po.status == POStatus.IN_TRANSIT
    assert in_transit_po.quantity_ordered == 500.0

