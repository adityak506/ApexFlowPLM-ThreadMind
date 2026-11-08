"""Mock ERP Backend Implementation.

Implements the ERPBackend interface using SQLite to manage inventory levels,
warehouse stock balances, and external supplier purchase orders.
"""

import sqlite3
from pathlib import Path
from erp_interface import (
    ERPBackend,
    ERPInventorySummary,
    ERPPurchaseOrder,
    ERPStockItem,
    POStatus,
)


class MockERPBackend(ERPBackend):
    """SQLite-backed mock ERP system."""

    def __init__(self, db_path: str = "plm_mock.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure ERP tables exist in the target database."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='erp_inventory'")
        if not cursor.fetchone():
            schema_path = Path(__file__).parent / "schema.sql"
            if schema_path.exists():
                with open(schema_path, "r", encoding="utf-8") as f:
                    ddl = f.read()
                self._conn.executescript(ddl)
                self._conn.commit()

    def close(self) -> None:
        """Close database connection."""
        if self._conn:
            self._conn.close()

    def get_stock(self, part_number: str) -> ERPInventorySummary:
        """Retrieve aggregated warehouse stock levels, bin locations, and total valuation."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT part_number, warehouse_code, warehouse_name, bin_location,
                   quantity_on_hand, quantity_reserved, quantity_available,
                   safety_stock, unit_cost, currency, last_counted
            FROM erp_inventory
            WHERE part_number = ?
            ORDER BY warehouse_code ASC
            """,
            (part_number,),
        )
        rows = cursor.fetchall()

        stock_locations = [
            ERPStockItem(
                part_number=row["part_number"],
                warehouse_code=row["warehouse_code"],
                warehouse_name=row["warehouse_name"],
                bin_location=row["bin_location"],
                quantity_on_hand=row["quantity_on_hand"],
                quantity_reserved=row["quantity_reserved"],
                quantity_available=row["quantity_available"],
                safety_stock=row["safety_stock"],
                unit_cost=row["unit_cost"],
                currency=row["currency"],
                last_counted=row["last_counted"],
            )
            for row in rows
        ]

        total_on_hand = sum(item.quantity_on_hand for item in stock_locations)
        total_reserved = sum(item.quantity_reserved for item in stock_locations)
        total_available = sum(item.quantity_available for item in stock_locations)
        total_valuation = sum(item.quantity_on_hand * item.unit_cost for item in stock_locations)
        currency = stock_locations[0].currency if stock_locations else "USD"

        return ERPInventorySummary(
            part_number=part_number,
            total_on_hand=total_on_hand,
            total_reserved=total_reserved,
            total_available=total_available,
            total_valuation=total_valuation,
            currency=currency,
            stock_locations=stock_locations,
        )

    def get_open_pos(self, part_number: str) -> list[ERPPurchaseOrder]:
        """Retrieve active and open purchase orders with suppliers for a part."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT po_number, line_number, part_number, supplier_name,
                   quantity_ordered, quantity_received, unit_price,
                   currency, order_date, expected_delivery, status
            FROM erp_purchase_orders
            WHERE part_number = ? AND status IN ('OPEN', 'IN_TRANSIT', 'HOLD')
            ORDER BY order_date DESC
            """,
            (part_number,),
        )
        rows = cursor.fetchall()

        return [
            ERPPurchaseOrder(
                po_number=row["po_number"],
                line_number=row["line_number"],
                part_number=row["part_number"],
                supplier_name=row["supplier_name"],
                quantity_ordered=row["quantity_ordered"],
                quantity_received=row["quantity_received"],
                unit_price=row["unit_price"],
                currency=row["currency"],
                order_date=row["order_date"],
                expected_delivery=row["expected_delivery"],
                status=POStatus(row["status"]),
            )
            for row in rows
        ]
