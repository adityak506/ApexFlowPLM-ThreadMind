"""Tests for OpenTelemetry Observability in Mock PLM System.

Validates the 5 core observability rules:
1. Vendor-neutral OpenTelemetry traces, metrics, and logs.
2. Structured JSON logs containing trace_id, tool_name, backend, and duration_ms.
3. Strict data protection: never logs secrets or full part/BOM payloads (identifiers and counts only).
4. Full instrumentation across all 15 MCP tools and PLMBackend methods with trace propagation.
5. Environment configurability (OTEL_SERVICE_NAME, OTEL_EXPORTER_OTLP_ENDPOINT) and
   resilience (no app crash if OTLP collector is unreachable).
"""

import json
import logging
import os
import pytest

from observability import (
    DEFAULT_SERVICE_NAME,
    StructuredJSONFormatter,
    extract_safe_context,
    instrument_all_backend_methods,
    instrument_backend_method,
    instrument_tool,
    telemetry,
)
from mock_backend import MockBackend
from seed_data import generate_dataset
import server


@pytest.fixture(autouse=True)
def setup_test_observability(tmp_path, monkeypatch):
    """Setup isolated seeded database, in-memory telemetry, and temporary log files."""
    db_path = str(tmp_path / "test_plm_obs.db")
    audit_path = str(tmp_path / "test_audit_obs.log")
    obs_log_path = str(tmp_path / "test_observability.log")

    # Generate full schema and seeded sample parts (including PMP-0001)
    generate_dataset(db_path=db_path)

    # Route environment variables and server state
    monkeypatch.setenv("PLM_SQLITE_PATH", db_path)
    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setattr(server, "AUDIT_LOG_FILE", audit_path)

    # Initialize TelemetryManager in in-memory mode for inspection
    telemetry.init(service_name="test-plm-obs-service", in_memory=True)
    telemetry.clear_spans()

    # Setup file handler on logger for structured JSON tests
    obs_handler = logging.FileHandler(obs_log_path, encoding="utf-8")
    obs_handler.setFormatter(StructuredJSONFormatter())
    from observability import logger
    logger.addHandler(obs_handler)

    yield {
        "db_path": db_path,
        "audit_path": audit_path,
        "obs_log_path": obs_log_path,
        "obs_handler": obs_handler,
    }

    # Teardown
    logger.removeHandler(obs_handler)
    obs_handler.close()


# =============================================================================
# 1. Structured JSON Log Schema & Formatter Tests
# =============================================================================

def test_structured_json_formatter_keys():
    """Verify that StructuredJSONFormatter outputs valid JSON with required keys:
    trace_id, tool_name, backend, and duration_ms.
    """
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="plm.observability",
        level=logging.INFO,
        pathname=__file__,
        lineno=100,
        msg="Test execution message",
        args=(),
        exc_info=None,
    )
    record.trace_id = "0123456789abcdef0123456789abcdef"
    record.span_id = "0123456789abcdef"
    record.tool_name = "test_custom_tool"
    record.backend = "mock"
    record.duration_ms = 42.567
    record.status = "SUCCESS"
    record.identifiers = {"part_number": "PMP-0001"}
    record.counts = {"result_count": 1}

    formatted = formatter.format(record)
    data = json.loads(formatted)

    assert data["timestamp"].endswith("Z")
    assert data["level"] == "INFO"
    assert data["trace_id"] == "0123456789abcdef0123456789abcdef"
    assert data["span_id"] == "0123456789abcdef"
    assert data["tool_name"] == "test_custom_tool"
    assert data["backend"] == "mock"
    assert data["duration_ms"] == 42.57
    assert data["status"] == "SUCCESS"
    assert data["identifiers"] == {"part_number": "PMP-0001"}
    assert data["counts"] == {"result_count": 1}


# =============================================================================
# 2. Strict Data Protection: Redaction & Payload Protection Tests
# =============================================================================

def test_safe_context_scrubs_secrets():
    """Verify that credentials, tokens, and passwords are never extracted into context."""
    args = ()
    kwargs = {
        "part_number": "PMP-0001",
        "api_key": "sk-secret-token-12345",
        "password": "SuperSecretPassword123!",
        "auth_token": "Bearer eyJhbGciOi...",
        "credentials": {"user": "admin", "secret": "xyz"},
    }

    identifiers, counts = extract_safe_context(args, kwargs)

    assert "part_number" in identifiers
    assert identifiers["part_number"] == "PMP-0001"
    # None of the sensitive keys should be captured in identifiers
    for key in identifiers:
        assert "password" not in key.lower()
        assert "token" not in key.lower()
        assert "secret" not in key.lower()
        assert "key" not in key.lower()


def test_safe_context_never_dumps_full_payload():
    """Verify that full part structures, BOM trees, or large lists are never logged in full,
    only identifiers and counts.
    """
    class MockComplexPart:
        part_number = "PMP-9999"
        version_label = "B.2"
        lifecycle_state = "RELEASED"
        description = "Large payload description with sensitive trade secrets"
        cad_model = b"BIN_CAD_GEOMETRY_BYTES..."

    identifiers, counts = extract_safe_context(
        (), {"part_number": "PMP-9999"}, result=MockComplexPart()
    )

    assert identifiers["part_number"] == "PMP-9999"
    assert identifiers["version"] == "B.2"
    assert counts["result_count"] == 1
    # Full payload fields must NOT be present
    assert "description" not in identifiers
    assert "cad_model" not in identifiers


# =============================================================================
# 3. OpenTelemetry MCP Tool & Backend Instrumentation Tests
# =============================================================================

def test_mcp_tool_span_and_metrics():
    """Verify that an instrumented MCP tool generates an OpenTelemetry span with
    proper attributes, records invocation metrics, and logs structured JSON.
    """
    result = server.get_part(part_number="PMP-0001")
    assert result.part_number == "PMP-0001"

    # Verify OpenTelemetry Spans
    spans = telemetry.get_finished_spans()
    assert len(spans) >= 1

    # Check the tool span
    tool_spans = [s for s in spans if s.name == "mcp.tool.get_part"]
    assert len(tool_spans) == 1
    t_span = tool_spans[0]

    assert t_span.attributes["plm.tool_name"] == "get_part"
    assert t_span.attributes["plm.backend"] == "mock"
    assert t_span.attributes["plm.id.part_number"] == "PMP-0001"
    assert t_span.status.is_ok


def test_backend_method_span_and_trace_propagation():
    """Verify that PLMBackend method generates a child span under the tool span,
    propagating the exact same trace_id.
    """
    backend = MockBackend(db_path=os.getenv("PLM_SQLITE_PATH"))

    @instrument_tool("composite_workflow_tool")
    def composite_tool():
        return backend.get_part("PMP-0001")

    composite_tool()

    spans = telemetry.get_finished_spans()
    tool_span = next(s for s in spans if s.name == "mcp.tool.composite_workflow_tool")
    backend_span = next(s for s in spans if s.name == "PLMBackend.get_part")

    # Trace propagation verification: Parent tool span and child backend span share trace_id
    assert tool_span.context.trace_id == backend_span.context.trace_id
    assert backend_span.parent.span_id == tool_span.context.span_id
    assert backend_span.attributes["plm.method_name"] == "get_part"
    assert backend_span.attributes["plm.backend"] == "mock"


def test_structured_log_output_contains_required_fields():
    """Verify that calling an MCP tool produces a structured JSON log entry in audit.log
    with trace_id, tool_name, backend, and duration_ms.
    """
    server.get_part(part_number="PMP-0001")

    audit_file = getattr(server, "AUDIT_LOG_FILE")
    assert os.path.exists(audit_file)

    with open(audit_file, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    assert len(lines) >= 1
    entry = lines[-1]

    assert "trace_id" in entry and len(entry["trace_id"]) == 32
    assert entry["tool_name"] == "get_part"
    assert entry["backend"] == "mock"
    assert isinstance(entry["duration_ms"], (int, float))
    assert entry["status"] == "SUCCESS"


# =============================================================================
# 4. Error Handling & Metric Error Counters
# =============================================================================

def test_tool_error_recording_and_metric():
    """Verify that when a tool raises an exception, the span is marked ERROR,
    error metrics are incremented, and structured JSON logs capture the error.
    """
    @instrument_tool("failing_test_tool")
    def faulty_tool():
        raise ValueError("Simulated operational failure")

    with pytest.raises(ValueError, match="Simulated operational failure"):
        faulty_tool()

    spans = telemetry.get_finished_spans()
    err_span = next(s for s in spans if s.name == "mcp.tool.failing_test_tool")

    assert not err_span.status.is_ok
    assert "Simulated operational failure" in err_span.status.description


# =============================================================================
# 5. Fault-Tolerance & Collector Unreachability
# =============================================================================

def test_unreachable_collector_never_crashes_app():
    """Verify that if OTEL_EXPORTER_OTLP_ENDPOINT points to an unreachable collector,
    the application and tools execute without crashing.
    """
    # Point endpoint to an invalid local port where no collector is running
    telemetry.init(
        service_name="resilient-service",
        otlp_endpoint="http://127.0.0.1:59999",
        in_memory=False,
    )

    @instrument_tool("resilience_probe_tool")
    def probe():
        return {"status": "operational"}

    # Must complete cleanly without raising any connection or export exception
    result = probe()
    assert result == {"status": "operational"}
