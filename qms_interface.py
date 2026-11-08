"""QMS Interface Definition.

Defines normalized Pydantic data models and the abstract QMSBackend
interface for interacting with Quality Management Systems (QMS)
(e.g., TrackWise, Veeva QMS, ETQ Reliance, or Mock SQLite QMS).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class DefectSeverity(str, Enum):
    """Quality defect severity rating."""
    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"


class DefectStatus(str, Enum):
    """Lifecycle status of a quality non-conformance report."""
    OPEN = "OPEN"
    UNDER_INVESTIGATION = "UNDER_INVESTIGATION"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class QMSDefectReport(BaseModel):
    """Represents a Quality Non-Conformance Report (NCR) or field failure ticket."""
    defect_number: str
    part_number: str
    title: str
    description: str
    severity: DefectSeverity = DefectSeverity.MAJOR
    status: DefectStatus = DefectStatus.OPEN
    failure_mode: str
    root_cause: str = ""
    linked_serial_numbers: list[str] = Field(default_factory=list)
    reported_by: str
    containment_action: str = ""
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class QMSBackend(ABC):
    """Abstract interface defining standard Quality Management System operations."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        try:
            from telemetry import instrument_all_adapter_methods
            instrument_all_adapter_methods("QMSBackend", cls)
        except Exception:
            pass

    @abstractmethod
    def get_defects(
        self,
        part_number: str | None = None,
        severity: str | None = None,
        status: str | None = None,
    ) -> list[QMSDefectReport]:
        """Query non-conformance and defect records filtered by part, severity, or lifecycle status.

        Args:
            part_number: Optional part number filter (e.g. 'PMP-0290').
            severity: Optional severity filter ('CRITICAL', 'MAJOR', 'MINOR').
            status: Optional status filter ('OPEN', 'UNDER_INVESTIGATION', 'CONTAINED', etc.).

        Returns:
            List of matching QMSDefectReport records.
        """
        pass

    @abstractmethod
    def get_defect_by_id(self, defect_number: str) -> QMSDefectReport | None:
        """Retrieve full details for a specific defect report by its unique tracking identifier.

        Args:
            defect_number: The unique defect identification code (e.g. 'DEF-2025-0042').

        Returns:
            QMSDefectReport instance or None if not found.
        """
        pass

