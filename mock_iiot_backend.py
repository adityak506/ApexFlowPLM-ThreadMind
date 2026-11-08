"""Mock IIoT Backend Implementation.

Implements the IIoTBackend interface using SQLite to manage equipment sensor
telemetry, threshold breach events, and edge gateway asset records.
"""

import json
import sqlite3
from pathlib import Path
from iiot_interface import (
    EventSeverity,
    IIoTBackend,
    IIoTDevice,
    IIoTSensorEvent,
    SensorType,
)


class MockIIoTBackend(IIoTBackend):
    """SQLite-backed mock Industrial IoT telemetry platform."""

    def __init__(self, db_path: str = "plm_mock.db"):
        self.db_path = db_path
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Ensure IIoT tables exist in the target database."""
        cursor = self._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='iiot_sensor_events'")
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

    def get_failure_events(
        self,
        part_number: str | None = None,
        serial_number: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[IIoTSensorEvent]:
        """Query real-time sensor failure events and telemetry anomalies."""
        query = """
            SELECT event_id, device_id, serial_number, part_number,
                   sensor_type, metric_name, metric_value, unit,
                   threshold_value, severity, event_type, timestamp, details
            FROM iiot_sensor_events
            WHERE 1=1
        """
        params: list[str | int] = []

        if part_number:
            query += " AND part_number = ?"
            params.append(part_number)
        if serial_number:
            query += " AND serial_number = ?"
            params.append(serial_number)
        if severity:
            query += " AND severity = ?"
            params.append(severity.upper())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor = self._conn.cursor()
        cursor.execute(query, params)
        rows = cursor.fetchall()

        return [
            IIoTSensorEvent(
                event_id=row["event_id"],
                device_id=row["device_id"],
                serial_number=row["serial_number"],
                part_number=row["part_number"],
                sensor_type=SensorType(row["sensor_type"]),
                metric_name=row["metric_name"],
                metric_value=row["metric_value"],
                unit=row["unit"],
                threshold_value=row["threshold_value"],
                severity=EventSeverity(row["severity"]),
                event_type=row["event_type"],
                timestamp=row["timestamp"],
                details=row["details"] or "",
            )
            for row in rows
        ]

    def get_device(self, serial_number: str) -> IIoTDevice | None:
        """Retrieve edge gateway health, installation metadata, and operating location."""
        cursor = self._conn.cursor()
        cursor.execute(
            """
            SELECT device_id, serial_number, asset_name, location,
                   installed_parts, status, last_ping
            FROM iiot_devices
            WHERE serial_number = ?
            """,
            (serial_number,),
        )
        row = cursor.fetchone()

        if not row:
            return None

        parts_raw = row["installed_parts"] or "[]"
        try:
            parts = json.loads(parts_raw)
        except Exception:
            parts = []

        return IIoTDevice(
            device_id=row["device_id"],
            serial_number=row["serial_number"],
            asset_name=row["asset_name"],
            location=row["location"],
            installed_parts=parts,
            status=row["status"],
            last_ping=row["last_ping"],
        )
