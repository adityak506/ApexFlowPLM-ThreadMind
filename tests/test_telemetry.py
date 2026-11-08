"""Comprehensive tests for OpenTelemetry Telemetry & Observability (telemetry.py).

Validates all 6 user requirements:
1. Initialize OpenTelemetry tracing, metrics, and logging from env vars with graceful fallback.
2. FastAPI instrumentation + custom RequestIDMiddleware injecting X-Request-ID.
3. @instrument_tool decorator and PLMBackend wrapper recording duration histograms,
   call counters, error counters, result counts, and spans with attributes
   (tool, backend, part_number ONLY as span attribute, NEVER as metric label).
4. Full distributed trace context propagation (API -> backend -> ERP/QMS/IIoT).
5. Custom business metrics:
   - threadmind_issues_detected_total{type}
   - threadmind_impact_analyses_total
   - threadmind_ecr_drafts_total{status=draft|confirmed|rejected}
6. Telemetry failures never break tool or backend execution.
"""

import json
import logging
import os
import pytest
from unittest.mock import MagicMock
from fastapi.testclient import TestClient

from telemetry import (
    DEFAULT_SERVICE_NAME,
    InstrumentedPLMBackend,
    RequestIDMiddleware,
    StructuredJSONFormatter,
    extract_safe_context,
    init_telemetry,
    instrument_adapter_method,
    instrument_all_adapter_methods,
    instrument_all_backend_methods,
    instrument_backend_method,
    instrument_tool,
    record_ecr_transition,
    record_impact_analysis,
    record_issue_detected,
    telemetry,
)
from mock_backend import MockBackend
from mock_erp_backend import MockERPBackend
from mock_qms_backend import MockQMSBackend
from mock_iiot_backend import MockIIoTBackend
from seed_data import generate_dataset
import server
from api import app, get_backend, get_erp_backend, get_qms_backend, get_iiot_backend


@pytest.fixture(autouse=True)
def setup_telemetry_env(tmp_path, monkeypatch):
    """Setup isolated seeded database, in-memory telemetry, and temporary log sinks."""
    db_path = str(tmp_path / "test_plm_telemetry.db")
    audit_path = str(tmp_path / "test_audit_telemetry.log")

    generate_dataset(db_path=db_path)

    monkeypatch.setenv("PLM_SQLITE_PATH", db_path)
    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setattr(server, "AUDIT_LOG_FILE", audit_path)

    # Initialize in-memory telemetry for inspection
    telemetry.init(service_name="test-telemetry-suite", in_memory=True)
    telemetry.clear_spans()

    yield {
        "db_path": db_path,
        "audit_path": audit_path,
    }


# =============================================================================
# 1. Telemetry Initialization & Fallback Tests
# =============================================================================

def test_telemetry_init_from_env_vars(monkeypatch):
    """Verify TelemetryManager initializes with custom env vars."""
    monkeypatch.setenv("OTEL_SERVICE_NAME", "custom-plm-env-service")
    telemetry.init(in_memory=True)
    assert telemetry.tracer is not None
    assert telemetry.meter is not None


def test_telemetry_collector_down_graceful_fallback():
    """Verify that if OTEL_EXPORTER_OTLP_ENDPOINT points to an unreachable collector,
    initialization and execution proceed without raising exceptions.
    """
    telemetry.init(
        service_name="resilient-collector-test",
        otlp_endpoint="http://127.0.0.1:59999",
        in_memory=False,
    )

    @instrument_tool("collector_fallback_probe")
    def probe(part_number: str):
        return {"part": part_number, "status": "ok"}

    result = probe(part_number="PMP-0001")
    assert result["status"] == "ok"


# =============================================================================
# 2. FastAPI Request ID Middleware & Instrumentation Tests
# =============================================================================

def test_request_id_middleware_generates_id(setup_telemetry_env):
    """Verify RequestIDMiddleware injects a generated X-Request-ID when not supplied."""
    client = TestClient(app)
    response = client.get("/parts?page=1&page_size=1")
    assert response.status_code == 200
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) >= 8


def test_request_id_middleware_preserves_id(setup_telemetry_env):
    """Verify RequestIDMiddleware preserves an incoming X-Request-ID header."""
    client = TestClient(app)
    custom_id = "req-custom-trace-uuid-9999"
    response = client.get("/parts?page=1&page_size=1", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Request-ID") == custom_id


# =============================================================================
# 3. @instrument_tool & PLMBackend Instrumentation Tests
# =============================================================================

def test_instrument_tool_records_span_and_metrics():
    """Verify @instrument_tool records duration, invocation count, result count,
    and span with attributes.
    """
    res = server.get_part(part_number="PMP-0001")
    assert res.part_number == "PMP-0001"

    spans = telemetry.get_finished_spans()
    tool_spans = [s for s in spans if s.name == "mcp.tool.get_part"]
    assert len(tool_spans) == 1
    span = tool_spans[0]

    assert span.attributes["tool"] == "get_part"
    assert span.attributes["backend"] == "mock"
    assert span.attributes["part_number"] == "PMP-0001"
    assert span.attributes["result_count"] == 1
    assert span.status.is_ok


def test_cardinality_guard_part_number_never_in_metric_labels():
    """CRITICAL RULE TEST: Verify part_number is NEVER included as a metric label.
    Part numbers have unbounded cardinality and must strictly remain span attributes only.
    """
    server.get_part(part_number="PMP-0001")
    server.where_used(part_number="PMP-0025")

    metrics_data = telemetry.get_metrics_data()
    assert metrics_data is not None

    for resource_metric in metrics_data.resource_metrics:
        for scope_metric in resource_metric.scope_metrics:
            for metric in scope_metric.metrics:
                # Inspect data points across sums, gauges, histograms
                data_points = []
                if hasattr(metric.data, "data_points"):
                    data_points = metric.data.data_points

                for dp in data_points:
                    labels = dict(dp.attributes)
                    assert "part_number" not in labels, (
                        f"VIOLATION: part_number found in metric '{metric.name}' labels: {labels}"
                    )
                    assert "p_no" not in labels
                    assert "clean_number" not in labels


def test_instrumented_plm_backend_wrapper(setup_telemetry_env):
    """Verify InstrumentedPLMBackend wrapper records spans and metrics for backend calls."""
    raw_backend = MockBackend(db_path=setup_telemetry_env["db_path"])
    wrapper = InstrumentedPLMBackend(raw_backend)

    part = wrapper.get_part("PMP-0001")
    assert part is not None
    assert part.part_number == "PMP-0001"

    spans = telemetry.get_finished_spans()
    backend_spans = [s for s in spans if s.name == "PLMBackend.get_part"]
    assert len(backend_spans) >= 1
    b_span = backend_spans[-1]

    assert b_span.attributes["method"] == "get_part"
    assert b_span.attributes["backend"] == "mock"
    assert b_span.attributes["part_number"] == "PMP-0001"
    raw_backend.close()


# =============================================================================
# 4. Distributed Trace Context Propagation Tests
# =============================================================================

def test_trace_propagation_across_layers(setup_telemetry_env):
    """Verify that a request flows as a single continuous trace across:
    FastAPI -> PLMBackend -> ERP -> QMS -> IIoT.
    """
    db_path = setup_telemetry_env["db_path"]
    test_backend = MockBackend(db_path=db_path)
    erp_backend = MockERPBackend(db_path=db_path)
    qms_backend = MockQMSBackend(db_path=db_path)
    iiot_backend = MockIIoTBackend(db_path=db_path)

    app.dependency_overrides[get_backend] = lambda: test_backend
    app.dependency_overrides[get_erp_backend] = lambda: erp_backend
    app.dependency_overrides[get_qms_backend] = lambda: qms_backend
    app.dependency_overrides[get_iiot_backend] = lambda: iiot_backend

    client = TestClient(app)
    response = client.get("/digital-thread/PMP-0290")
    assert response.status_code == 200

    spans = telemetry.get_finished_spans()
    assert len(spans) >= 4

    # All spans created during this request must share the same trace_id
    trace_ids = {s.context.trace_id for s in spans}
    assert len(trace_ids) == 1, f"Expected 1 trace_id, found multiple: {trace_ids}"

    span_names = {s.name for s in spans}
    assert "PLMBackend.get_part" in span_names
    assert "ERPBackend.get_stock" in span_names
    assert "QMSBackend.get_defects" in span_names
    assert "IIoTBackend.get_failure_events" in span_names

    app.dependency_overrides.clear()
    test_backend.close()
    erp_backend.close()
    qms_backend.close()
    iiot_backend.close()


# =============================================================================
# 5. Custom Business Metrics Tests
# =============================================================================

def test_custom_business_metrics_recording():
    """Verify that custom business metrics are accurately recorded:
    - threadmind_issues_detected_total{type}
    - threadmind_impact_analyses_total
    - threadmind_ecr_drafts_total{status=draft|confirmed|rejected}
    """
    # 1. Issues detected
    record_issue_detected("duplicates", count=5)
    record_issue_detected("obsolete_in_released", count=8)

    # 2. Impact analyses
    record_impact_analysis(count=1)

    # 3. ECR transitions
    record_ecr_transition("draft", count=1)
    record_ecr_transition("confirmed", count=1)
    record_ecr_transition("rejected", count=1)

    metrics_data = telemetry.get_metrics_data()
    assert metrics_data is not None

    found_metrics = {}
    for rm in metrics_data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                found_metrics[m.name] = m

    assert "threadmind_issues_detected_total" in found_metrics
    assert "threadmind_impact_analyses_total" in found_metrics
    assert "threadmind_ecr_drafts_total" in found_metrics

    # Check ECR metric status labels
    ecr_m = found_metrics["threadmind_ecr_drafts_total"]
    ecr_statuses = {dp.attributes.get("status") for dp in ecr_m.data.data_points}
    assert "draft" in ecr_statuses
    assert "confirmed" in ecr_statuses
    assert "rejected" in ecr_statuses

    # Check issues detected metric type labels
    issue_m = found_metrics["threadmind_issues_detected_total"]
    issue_types = {dp.attributes.get("type") for dp in issue_m.data.data_points}
    assert "duplicates" in issue_types
    assert "obsolete_in_released" in issue_types


# =============================================================================
# 6. Telemetry Failures Never Break Tool Execution Tests
# =============================================================================

def test_tracer_failure_never_breaks_tool():
    """Verify that if the OpenTelemetry tracer raises an exception, the MCP tool
    executes successfully and returns normal results.
    """
    # Mock tracer.start_span to raise an unhandled exception
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(telemetry.tracer, "start_span", MagicMock(side_effect=RuntimeError("Tracer memory fault")))

        @instrument_tool("probe_with_broken_tracer")
        def robust_tool(part_number: str):
            return {"part": part_number, "data": "valid_output"}

        result = robust_tool(part_number="PMP-0001")
        assert result == {"part": "PMP-0001", "data": "valid_output"}


def test_metrics_failure_never_breaks_tool():
    """Verify that if metric counter or histogram recording raises an exception,
    tool execution succeeds unimpeded.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(telemetry, "record_tool_metrics", MagicMock(side_effect=RuntimeError("Metrics storage full")))

        @instrument_tool("probe_with_broken_metrics")
        def robust_tool(part_number: str):
            return {"part": part_number, "data": "valid_output"}

        result = robust_tool(part_number="PMP-0001")
        assert result == {"part": "PMP-0001", "data": "valid_output"}


def test_backend_telemetry_failure_never_breaks_backend(setup_telemetry_env):
    """Verify that if telemetry fails inside a PLMBackend method, the backend
    returns correct data without raising.
    """
    backend = MockBackend(db_path=setup_telemetry_env["db_path"])

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(telemetry, "record_backend_metrics", MagicMock(side_effect=RuntimeError("Telemetry pipe broken")))

        part = backend.get_part("PMP-0001")
        assert part is not None
        assert part.part_number == "PMP-0001"

    backend.close()

