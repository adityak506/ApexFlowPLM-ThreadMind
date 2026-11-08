"""IIoT Interface Definition.

Defines normalized Pydantic data models and the abstract IIoTBackend
interface for interacting with Industrial Internet of Things (IIoT) backends
(e.g., PTC ThingWorx, AWS IoT SiteWise, Azure IoT Hub, or Mock SQLite IIoT).
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class SensorType(str, Enum):
    """Classification of industrial sensor transducers."""
    VIBRATION = "VIBRATION"
    TEMPERATURE = "TEMPERATURE"
    PRESSURE = "PRESSURE"
    FLOW_RATE = "FLOW_RATE"
    ACOUSTIC = "ACOUSTIC"


class EventSeverity(str, Enum):
    """Telemetry anomaly urgency level."""
    CRITICAL = "CRITICAL"
    WARNING = "WARNING"
    INFO = "INFO"


class IIoTDevice(BaseModel):
    """Represents an edge gateway or physical asset connected to the IIoT network."""
    device_id: str
    serial_number: str
    asset_name: str
    location: str
    installed_parts: list[str] = Field(default_factory=list)
    status: str = "ONLINE"
    last_ping: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


class IIoTSensorEvent(BaseModel):
    """Represents a real-time sensor failure event, threshold breach, or anomaly alert."""
    event_id: str
    device_id: str
    serial_number: str
    part_number: str
    sensor_type: SensorType
    metric_name: str
    metric_value: float
    unit: str
    threshold_value: float
    severity: EventSeverity = EventSeverity.WARNING
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    details: str = ""


class IIoTBackend(ABC):
    """Abstract interface defining standard Industrial IoT telemetry operations."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        try:
            from telemetry import instrument_all_adapter_methods
            instrument_all_adapter_methods("IIoTBackend", cls)
        except Exception:
            pass

    @abstractmethod
    def get_failure_events(
        self,
        part_number: str | None = None,
        serial_number: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[IIoTSensorEvent]:
        """Query real-time sensor failure events and telemetry anomalies.

        Args:
            part_number: Optional part number filter (e.g. 'PMP-0290').
            serial_number: Optional equipment serial number (e.g. 'SN-APX-2025-001').
            severity: Optional urgency filter ('CRITICAL', 'WARNING', 'INFO').
            limit: Maximum number of events to return (default 50).

        Returns:
            List of matching IIoTSensorEvent records.
        """
        pass

    @abstractmethod
    def get_device(self, serial_number: str) -> IIoTDevice | None:
        """Retrieve edge gateway health, installation metadata, and operating location.

        Args:
            serial_number: Asset equipment serial number (e.g. 'SN-APX-2025-001').

        Returns:
            IIoTDevice record or None if not found.
        """
        pass

