"""ERP Interface Definition.

Defines the normalized Pydantic data models and the abstract ERPBackend
interface for interacting with Enterprise Resource Planning (ERP) backends
(e.g., SAP, Oracle NetSuite, or Mock SQLite ERP).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class POStatus(str, Enum):
    """Purchase Order lifecycle statuses."""
    OPEN = "OPEN"
    IN_TRANSIT = "IN_TRANSIT"
    RECEIVED = "RECEIVED"
    CANCELLED = "CANCELLED"
    HOLD = "HOLD"


class ERPStockItem(BaseModel):
    """Represents inventory on-hand in a specific warehouse and storage bin."""
    part_number: str
    warehouse_code: str
    warehouse_name: str
    bin_location: str
    quantity_on_hand: float
    quantity_reserved: float
    quantity_available: float
    safety_stock: float = 0.0
    unit_cost: float = 0.0
    currency: str = "USD"
    last_counted: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class ERPInventorySummary(BaseModel):
    """Aggregated inventory balance and valuation across all enterprise facilities."""
    part_number: str
    total_on_hand: float
    total_reserved: float
    total_available: float
    total_valuation: float
    currency: str = "USD"
    stock_locations: list[ERPStockItem] = Field(default_factory=list)


class ERPPurchaseOrder(BaseModel):
    """Represents a purchase order line commitment with an external supplier."""
    po_number: str
    line_number: int = 1
    part_number: str
    supplier_name: str
    quantity_ordered: float
    quantity_received: float = 0.0
    unit_price: float
    currency: str = "USD"
    order_date: str
    expected_delivery: str
    status: POStatus = POStatus.OPEN


class ERPBackend(ABC):
    """Abstract interface defining standard ERP inventory and procurement operations."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        try:
            from telemetry import instrument_all_adapter_methods
            instrument_all_adapter_methods("ERPBackend", cls)
        except Exception:
            pass

    @abstractmethod
    def get_stock(self, part_number: str) -> ERPInventorySummary:
        """Retrieve aggregated warehouse stock levels, bin locations, and total valuation for a part.

        Args:
            part_number: Unique part identification number (e.g. 'PMP-0290').

        Returns:
            ERPInventorySummary detailing balances per warehouse and total on hand/available.
        """
        pass

    @abstractmethod
    def get_open_pos(self, part_number: str) -> list[ERPPurchaseOrder]:
        """Retrieve active and open purchase orders with suppliers for a part.

        Args:
            part_number: Unique part identification number (e.g. 'PMP-0290').

        Returns:
            List of ERPPurchaseOrder records in OPEN, IN_TRANSIT, or HOLD status.
        """
        pass

