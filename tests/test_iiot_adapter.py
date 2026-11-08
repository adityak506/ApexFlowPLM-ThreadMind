"""Tests for IIoT models and MockIIoTBackend."""

import pytest
from iiot_interface import (
    EventSeverity,
    IIoTDevice,
    IIoTSensorEvent,
    SensorType,
)
from mock_iiot_backend import MockIIoTBackend


@pytest.fixture
def iiot_backend():
    return MockIIoTBackend(db_path="plm_mock.db")


def test_iiot_models():
    event = IIoTSensorEvent(
        event_id="EVT-01",
        device_id="DEV-01",
        serial_number="SN-01",
        part_number="PMP-0290",
        sensor_type=SensorType.VIBRATION,
        metric_name="vibration_rms",
        metric_value=12.5,
        unit="mm/s",
        threshold_value=4.5,
        severity=EventSeverity.CRITICAL,
        event_type="THRESHOLD_EXCEEDED",
    )
    assert event.event_id == "EVT-01"
    assert event.metric_value == 12.5
    assert event.severity == EventSeverity.CRITICAL

    device = IIoTDevice(
        device_id="DEV-01",
        serial_number="SN-01",
        asset_name="Test Pump",
        location="Site Alpha",
        installed_parts=["PMP-0290"],
    )
    assert device.asset_name == "Test Pump"
    assert "PMP-0290" in device.installed_parts


def test_iiot_get_failure_events(iiot_backend):
    events = iiot_backend.get_failure_events(part_number="PMP-0290")
    assert len(events) >= 3

    critical_events = iiot_backend.get_failure_events(
        part_number="PMP-0290", severity="CRITICAL"
    )
    assert len(critical_events) == 2
    types = {e.sensor_type for e in critical_events}
    assert SensorType.VIBRATION in types
    assert SensorType.TEMPERATURE in types


def test_iiot_get_failure_events_by_serial(iiot_backend):
    events = iiot_backend.get_failure_events(serial_number="SN-APX-2025-001")
    assert len(events) >= 3
    assert all(e.serial_number == "SN-APX-2025-001" for e in events)


def test_iiot_get_device(iiot_backend):
    device = iiot_backend.get_device("SN-APX-2025-001")
    assert device is not None
    assert device.device_id == "EDGE-GATEWAY-101"
    assert device.status == "CRITICAL"
    assert "PMP-0290" in device.installed_parts

    missing = iiot_backend.get_device("NON_EXISTENT_SERIAL")
    assert missing is None

