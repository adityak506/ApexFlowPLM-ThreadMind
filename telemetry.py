"""OpenTelemetry Telemetry and Observability Module for Mock PLM System.

Fulfills all system observability requirements:
1. Initializes OpenTelemetry tracing, metrics, and structured logging from env vars,
   with graceful fallback if the OTLP collector is unavailable.
2. FastAPI instrumentation and RequestIDMiddleware injecting 'X-Request-ID'.
3. @instrument_tool decorator and PLMBackend wrapper recording duration histograms,
   call counters, error counters, result counts, and spans with attributes
   (tool, backend, and part_number ONLY as span attributes, NEVER as metric labels).
4. Full distributed trace context propagation (UI -> API -> LLM -> MCP tool -> backend -> adapters).
5. Custom business metrics:
   - threadmind_issues_detected_total{type}
   - threadmind_impact_analyses_total
   - threadmind_ecr_drafts_total{status=draft|confirmed|rejected}
6. Strict fault-tolerance: telemetry failures NEVER crash or interrupt tool execution.
"""

from __future__ import annotations

from contextlib import contextmanager
import contextvars
import inspect
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Generator, TypeVar

# OpenTelemetry API & SDK
from opentelemetry import metrics, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.trace import StatusCode, format_trace_id, format_span_id

# Starlette / FastAPI
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

F = TypeVar("F", bound=Callable[..., Any])

# =============================================================================
# Constants, ContextVars & Environment Configuration
# =============================================================================

DEFAULT_SERVICE_NAME = "mock-plm-server"
DEFAULT_LOG_FILE = os.getenv("PLM_LOG_FILE", "observability.log")
DEFAULT_AUDIT_LOG_FILE = os.getenv("PLM_AUDIT_LOG_FILE", "audit.log")

SENSITIVE_KEY_SUBSTRINGS = (
    "password",
    "token",
    "secret",
    "credential",
    "api_key",
    "apikey",
    "auth",
    "bearer",
    "private_key",
)

# ContextVar for propagating request_id across async and sync call chains
request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="")


# =============================================================================
# Structured JSON Log Formatter
# =============================================================================

class StructuredJSONFormatter(logging.Formatter):
    """Formats log records as structured, single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        # Extract trace and span IDs if active
        trace_id_str = getattr(record, "trace_id", "")
        span_id_str = getattr(record, "span_id", "")

        if not trace_id_str:
            try:
                current_span = trace.get_current_span()
                span_ctx = current_span.get_span_context() if current_span else None
                if span_ctx and span_ctx.is_valid:
                    trace_id_str = format_trace_id(span_ctx.trace_id)
                    span_id_str = format_span_id(span_ctx.span_id)
            except Exception:
                pass

        req_id = getattr(record, "request_id", "") or request_id_ctx.get("")

        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "message": record.getMessage(),
            "trace_id": trace_id_str,
            "span_id": span_id_str,
            "request_id": req_id,
            "tool_name": getattr(record, "tool_name", ""),
            "tool": getattr(record, "tool", getattr(record, "tool_name", "")),
            "backend": getattr(record, "backend", "unknown"),
            "duration_ms": round(float(getattr(record, "duration_ms", 0.0)), 2),
            "status": getattr(record, "status", "INFO"),
        }

        # Safe identifiers & counts only
        identifiers = getattr(record, "identifiers", None)
        if identifiers and isinstance(identifiers, dict):
            log_obj["identifiers"] = identifiers

        counts = getattr(record, "counts", None)
        if counts and isinstance(counts, dict):
            log_obj["counts"] = counts

        error_detail = getattr(record, "error", None)
        if error_detail:
            log_obj["error"] = str(error_detail)

        return json.dumps(log_obj, ensure_ascii=False)


# Initialize Structured Logger
logger = logging.getLogger("plm.telemetry")
logger.setLevel(logging.INFO)
logger.propagate = False

_file_handler_installed = False
for h in logger.handlers:
    if isinstance(h, logging.FileHandler):
        _file_handler_installed = True
        break

if not _file_handler_installed:
    try:
        fh = logging.FileHandler(DEFAULT_LOG_FILE, encoding="utf-8")
        fh.setFormatter(StructuredJSONFormatter())
        logger.addHandler(fh)
    except Exception as exc:
        print(f"[Telemetry Warning] Could not open {DEFAULT_LOG_FILE}: {exc}", file=sys.stderr)


# =============================================================================
# OpenTelemetry State & Initializer
# =============================================================================

class TelemetryManager:
    """Manages OpenTelemetry TracerProvider, MeterProvider, and Metrics Instruments."""

    def __init__(self) -> None:
        self.tracer_provider: TracerProvider | None = None
        self.meter_provider: MeterProvider | None = None
        self.tracer: trace.Tracer = trace.get_tracer("plm.telemetry")
        self.meter: metrics.Meter = metrics.get_meter("plm.telemetry")

        # Test inspection handles
        self.in_memory_span_exporter: InMemorySpanExporter | None = None
        self.in_memory_metric_reader: InMemoryMetricReader | None = None

        # Standard Tool Metrics
        self._tool_calls_counter: metrics.Counter | None = None
        self._tool_duration_histogram: metrics.Histogram | None = None
        self._tool_errors_counter: metrics.Counter | None = None
        self._tool_result_count_histogram: metrics.Histogram | None = None

        # Standard Backend Metrics
        self._backend_calls_counter: metrics.Counter | None = None
        self._backend_duration_histogram: metrics.Histogram | None = None
        self._backend_errors_counter: metrics.Counter | None = None
        self._backend_result_count_histogram: metrics.Histogram | None = None

        # Custom Business Metrics
        self._issues_detected_counter: metrics.Counter | None = None
        self._impact_analyses_counter: metrics.Counter | None = None
        self._ecr_drafts_counter: metrics.Counter | None = None

        # LLM & Agent Loop Metrics
        self._llm_tokens_counter: metrics.Counter | None = None
        self._llm_latency_histogram: metrics.Histogram | None = None
        self._llm_ttft_histogram: metrics.Histogram | None = None
        self._llm_estimated_cost_counter: metrics.Counter | None = None
        self._agent_tool_calls_counter: metrics.Counter | None = None
        self._agent_tool_calls_failed_counter: metrics.Counter | None = None
        self._agent_turns_counter: metrics.Counter | None = None
        self._agent_quality_issues_counter: metrics.Counter | None = None

        # Auto-initialize from environment variables
        self.init()

    def init(
        self,
        service_name: str | None = None,
        otlp_endpoint: str | None = None,
        in_memory: bool = False,
    ) -> None:
        """Initialize or reconfigure OpenTelemetry components safely with fallback."""
        svc_name = service_name or os.getenv("OTEL_SERVICE_NAME", DEFAULT_SERVICE_NAME)
        endpoint = (
            otlp_endpoint
            if otlp_endpoint is not None
            else os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
        )

        resource = Resource.create({"service.name": svc_name, "service.version": "1.0.0"})

        # 1. Setup TracerProvider
        tp = TracerProvider(resource=resource)
        self.in_memory_span_exporter = None

        if in_memory:
            self.in_memory_span_exporter = InMemorySpanExporter()
            tp.add_span_processor(SimpleSpanProcessor(self.in_memory_span_exporter))
        elif endpoint:
            try:
                if endpoint.startswith("http://") or endpoint.startswith("https://") or "4318" in endpoint:
                    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                        OTLPSpanExporter as OTLPHttpSpanExporter,
                    )
                    span_exporter = OTLPHttpSpanExporter(endpoint=endpoint, timeout=3)
                else:
                    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                        OTLPSpanExporter as OTLPGrpcSpanExporter,
                    )
                    span_exporter = OTLPGrpcSpanExporter(endpoint=endpoint, timeout=3)

                tp.add_span_processor(BatchSpanProcessor(span_exporter))
            except Exception as e:
                # Graceful fallback: never crash if collector setup fails
                print(f"[Telemetry Warning] Failed to initialize OTLP Span Exporter ({endpoint}): {e}", file=sys.stderr)

        self.tracer_provider = tp
        try:
            trace._TRACER_PROVIDER = None
            if hasattr(trace, "_TRACER_PROVIDER_SET_ONCE"):
                trace._TRACER_PROVIDER_SET_ONCE._done = False
            trace.set_tracer_provider(tp)
        except Exception:
            pass
        self.tracer = tp.get_tracer("plm.telemetry")

        # 2. Setup MeterProvider
        metric_readers = []
        self.in_memory_metric_reader = None

        if in_memory:
            self.in_memory_metric_reader = InMemoryMetricReader()
            metric_readers.append(self.in_memory_metric_reader)
        elif endpoint:
            try:
                if endpoint.startswith("http://") or endpoint.startswith("https://") or "4318" in endpoint:
                    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                        OTLPMetricExporter as OTLPHttpMetricExporter,
                    )
                    metric_exporter = OTLPHttpMetricExporter(endpoint=endpoint, timeout=3)
                else:
                    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                        OTLPMetricExporter as OTLPGrpcMetricExporter,
                    )
                    metric_exporter = OTLPGrpcMetricExporter(endpoint=endpoint, timeout=3)

                metric_readers.append(PeriodicExportingMetricReader(metric_exporter, export_interval_millis=30000))
            except Exception as e:
                print(f"[Telemetry Warning] Failed to initialize OTLP Metric Exporter ({endpoint}): {e}", file=sys.stderr)

        mp = MeterProvider(resource=resource, metric_readers=metric_readers)
        self.meter_provider = mp
        try:
            import opentelemetry.metrics._internal as mi
            mi._METER_PROVIDER = None
            mi._METER_PROVIDER_SET_ONCE._done = False
            metrics.set_meter_provider(mp)
        except Exception:
            pass
        self.meter = mp.get_meter("plm.telemetry")

        # 3. Create Standard Metric Instruments
        self._tool_calls_counter = self.meter.create_counter(
            name="plm_tool_calls_total",
            description="Total count of MCP tool invocations",
            unit="1",
        )
        self._tool_duration_histogram = self.meter.create_histogram(
            name="plm_tool_duration_seconds",
            description="Execution duration of MCP tool calls in seconds",
            unit="s",
        )
        self._tool_errors_counter = self.meter.create_counter(
            name="plm_tool_errors_total",
            description="Total count of MCP tool execution failures",
            unit="1",
        )
        self._tool_result_count_histogram = self.meter.create_histogram(
            name="plm_tool_result_count",
            description="Result count returned by MCP tool execution",
            unit="1",
        )

        self._backend_calls_counter = self.meter.create_counter(
            name="plm_backend_calls_total",
            description="Total count of PLMBackend method calls",
            unit="1",
        )
        self._backend_duration_histogram = self.meter.create_histogram(
            name="plm_backend_duration_seconds",
            description="Execution duration of PLMBackend methods in seconds",
            unit="s",
        )
        self._backend_errors_counter = self.meter.create_counter(
            name="plm_backend_errors_total",
            description="Total count of PLMBackend method errors",
            unit="1",
        )
        self._backend_result_count_histogram = self.meter.create_histogram(
            name="plm_backend_result_count",
            description="Result count returned by PLMBackend method execution",
            unit="1",
        )

        # 4. Create Custom Business Metrics
        self._issues_detected_counter = self.meter.create_counter(
            name="threadmind_issues_detected_total",
            description="Total count of planted or detected quality/compliance issues",
            unit="1",
        )
        self._impact_analyses_counter = self.meter.create_counter(
            name="threadmind_impact_analyses_total",
            description="Total count of change impact blast radius analyses performed",
            unit="1",
        )
        self._ecr_drafts_counter = self.meter.create_counter(
            name="threadmind_ecr_drafts_total",
            description="Total count of ECR lifecycle transitions",
            unit="1",
        )

        # 5. Create LLM & Agent Loop Metric Instruments
        self._llm_tokens_counter = self.meter.create_counter(
            name="threadmind_llm_tokens_total",
            description="Total count of LLM tokens processed (in/out)",
            unit="1",
        )
        self._llm_latency_histogram = self.meter.create_histogram(
            name="threadmind_llm_latency_seconds",
            description="Latency of LLM calls in seconds",
            unit="s",
        )
        self._llm_ttft_histogram = self.meter.create_histogram(
            name="threadmind_llm_time_to_first_token_seconds",
            description="Time to first token (TTFT) for LLM streaming responses in seconds",
            unit="s",
        )
        self._llm_estimated_cost_counter = self.meter.create_counter(
            name="threadmind_llm_estimated_cost_usd_total",
            description="Estimated cost of LLM queries in USD based on configurable pricing table",
            unit="USD",
        )
        self._agent_tool_calls_counter = self.meter.create_counter(
            name="threadmind_agent_tool_calls_total",
            description="Total count of tool calls dispatched by the AI agent loop",
            unit="1",
        )
        self._agent_tool_calls_failed_counter = self.meter.create_counter(
            name="threadmind_agent_tool_calls_failed_total",
            description="Total count of tool calls that failed in the AI agent loop",
            unit="1",
        )
        self._agent_turns_counter = self.meter.create_counter(
            name="threadmind_agent_turns_total",
            description="Total number of reasoning turns executed by the AI agent loop",
            unit="1",
        )
        self._agent_quality_issues_counter = self.meter.create_counter(
            name="threadmind_agent_quality_issues_total",
            description="Total count of agent quality degradation events (rejected draft, max turns exceeded)",
            unit="1",
        )

    # -------------------------------------------------------------------------
    # Metric Recording Handlers (Guaranteed Non-Crashing)
    # -------------------------------------------------------------------------

    def record_tool_metrics(
        self, tool_name: str, backend: str, status: str, duration_sec: float, result_count: int = 0
    ) -> None:
        """Safely record tool metrics without raising. part_number is NEVER passed as a label."""
        try:
            # Low-cardinality labels only
            attrs = {"tool": tool_name, "backend": backend, "status": status}
            if self._tool_calls_counter:
                self._tool_calls_counter.add(1, attrs)
            if self._tool_duration_histogram:
                self._tool_duration_histogram.record(duration_sec, {"tool": tool_name, "backend": backend})
            if self._tool_result_count_histogram and result_count >= 0:
                self._tool_result_count_histogram.record(result_count, {"tool": tool_name, "backend": backend})
            if status == "error" and self._tool_errors_counter:
                self._tool_errors_counter.add(1, {"tool": tool_name, "backend": backend})
        except Exception:
            pass

    def record_backend_metrics(
        self, method_name: str, backend: str, status: str, duration_sec: float, result_count: int = 0
    ) -> None:
        """Safely record backend metrics without raising. part_number is NEVER passed as a label."""
        try:
            attrs = {"method": method_name, "backend": backend, "status": status}
            if self._backend_calls_counter:
                self._backend_calls_counter.add(1, attrs)
            if self._backend_duration_histogram:
                self._backend_duration_histogram.record(duration_sec, {"method": method_name, "backend": backend})
            if self._backend_result_count_histogram and result_count >= 0:
                self._backend_result_count_histogram.record(result_count, {"method": method_name, "backend": backend})
            if status == "error" and self._backend_errors_counter:
                self._backend_errors_counter.add(1, {"method": method_name, "backend": backend})
        except Exception:
            pass

    def record_issue_detected(self, issue_type: str, count: int = 1) -> None:
        """Record custom business metric for detected issues: threadmind_issues_detected_total{type}."""
        try:
            if self._issues_detected_counter and count > 0:
                self._issues_detected_counter.add(count, {"type": str(issue_type)})
        except Exception:
            pass

    def record_impact_analysis(self, count: int = 1) -> None:
        """Record custom business metric: threadmind_impact_analyses_total."""
        try:
            if self._impact_analyses_counter and count > 0:
                self._impact_analyses_counter.add(count)
        except Exception:
            pass

    def record_ecr_transition(self, status: str, count: int = 1) -> None:
        """Record custom business metric: threadmind_ecr_drafts_total{status=draft|confirmed|rejected}."""
        try:
            clean_status = str(status).lower()
            if clean_status not in ("draft", "confirmed", "rejected"):
                clean_status = "draft"
            if self._ecr_drafts_counter and count > 0:
                self._ecr_drafts_counter.add(count, {"status": clean_status})
        except Exception:
            pass

    def record_llm_tokens(self, model: str, token_type: str, count: int) -> None:
        """Record input or output tokens for an LLM call: threadmind_llm_tokens_total{model, type}."""
        try:
            if self._llm_tokens_counter and count > 0:
                clean_type = "input" if "in" in str(token_type).lower() else "output"
                self._llm_tokens_counter.add(count, {"model": str(model).lower(), "type": clean_type})
        except Exception:
            pass

    def record_llm_latency(self, model: str, latency_sec: float) -> None:
        """Record LLM call latency histogram: threadmind_llm_latency_seconds{model}."""
        try:
            if self._llm_latency_histogram and latency_sec >= 0:
                self._llm_latency_histogram.record(latency_sec, {"model": str(model).lower()})
        except Exception:
            pass

    def record_llm_ttft(self, model: str, ttft_sec: float) -> None:
        """Record time to first token histogram: threadmind_llm_time_to_first_token_seconds{model}."""
        try:
            if self._llm_ttft_histogram and ttft_sec >= 0:
                self._llm_ttft_histogram.record(ttft_sec, {"model": str(model).lower()})
        except Exception:
            pass

    def record_llm_cost(self, model: str, cost_usd: float) -> None:
        """Record estimated LLM cost counter: threadmind_llm_estimated_cost_usd_total{model}."""
        try:
            if self._llm_estimated_cost_counter and cost_usd > 0:
                self._llm_estimated_cost_counter.add(cost_usd, {"model": str(model).lower()})
        except Exception:
            pass

    def record_agent_tool_call(self, tool_name: str, status: str = "success") -> None:
        """Record tool call in conversation: threadmind_agent_tool_calls_total{tool, status}."""
        try:
            if self._agent_tool_calls_counter:
                self._agent_tool_calls_counter.add(1, {"tool": str(tool_name), "status": str(status).lower()})
        except Exception:
            pass

    def record_agent_tool_failed(self, tool_name: str) -> None:
        """Record failed tool call: threadmind_agent_tool_calls_failed_total{tool}."""
        try:
            if self._agent_tool_calls_failed_counter:
                self._agent_tool_calls_failed_counter.add(1, {"tool": str(tool_name)})
        except Exception:
            pass

    def record_agent_turns(self, model: str = "default", turns: int = 1) -> None:
        """Record agent reasoning turns: threadmind_agent_turns_total{model}."""
        try:
            if self._agent_turns_counter and turns > 0:
                self._agent_turns_counter.add(turns, {"model": str(model).lower()})
        except Exception:
            pass

    def record_agent_quality_issue(self, reason: str, count: int = 1) -> None:
        """Record agent quality degradation metric: threadmind_agent_quality_issues_total{reason=rejected_draft|max_turns_exceeded}."""
        try:
            clean_reason = str(reason).lower()
            if clean_reason not in ("rejected_draft", "max_turns_exceeded"):
                clean_reason = "rejected_draft" if "reject" in clean_reason else "max_turns_exceeded"
            if self._agent_quality_issues_counter and count > 0:
                self._agent_quality_issues_counter.add(count, {"reason": clean_reason})
        except Exception:
            pass

    # -------------------------------------------------------------------------
    # Test Inspection Helpers
    # -------------------------------------------------------------------------

    def get_finished_spans(self) -> list[Any]:
        """Retrieve finished spans from in-memory exporter."""
        if self.in_memory_span_exporter:
            return list(self.in_memory_span_exporter.get_finished_spans())
        return []

    def clear_spans(self) -> None:
        """Clear recorded spans from in-memory exporter."""
        if self.in_memory_span_exporter:
            self.in_memory_span_exporter.clear()

    def get_metrics_data(self) -> Any:
        """Retrieve metrics data from in-memory reader."""
        if self.in_memory_metric_reader:
            return self.in_memory_metric_reader.get_metrics_data()
        return None


# Global Telemetry Instance
telemetry = TelemetryManager()


# Convenience wrappers for business metrics
def record_issue_detected(issue_type: str, count: int = 1) -> None:
    telemetry.record_issue_detected(issue_type, count)


def record_impact_analysis(count: int = 1) -> None:
    telemetry.record_impact_analysis(count)


def record_ecr_transition(status: str, count: int = 1) -> None:
    telemetry.record_ecr_transition(status, count)


# Convenience wrappers for LLM & Agent metrics
def record_llm_tokens(model: str, token_type: str, count: int) -> None:
    telemetry.record_llm_tokens(model, token_type, count)


def record_llm_latency(model: str, latency_sec: float) -> None:
    telemetry.record_llm_latency(model, latency_sec)


def record_llm_ttft(model: str, ttft_sec: float) -> None:
    telemetry.record_llm_ttft(model, ttft_sec)


def record_llm_cost(model: str, cost_usd: float) -> None:
    telemetry.record_llm_cost(model, cost_usd)


def record_agent_tool_call(tool_name: str, status: str = "success") -> None:
    telemetry.record_agent_tool_call(tool_name, status)


def record_agent_tool_failed(tool_name: str) -> None:
    telemetry.record_agent_tool_failed(tool_name)


def record_agent_turns(model: str = "default", turns: int = 1) -> None:
    telemetry.record_agent_turns(model, turns)


def record_agent_quality_issue(reason: str, count: int = 1) -> None:
    telemetry.record_agent_quality_issue(reason, count)


def is_prompt_capture_enabled() -> bool:
    """Return True if prompt contents capture is explicitly enabled via OTEL_CAPTURE_PROMPTS=true.
    Defaults to False to prevent accidental exposure of sensitive engineering trade secrets in telemetry.
    """
    val = os.getenv("OTEL_CAPTURE_PROMPTS", "false").strip().lower()
    return val in ("true", "1", "yes", "on")


def redact_prompt(prompt: str) -> str:
    """Redact prompt content unless OTEL_CAPTURE_PROMPTS is explicitly set to true."""
    if is_prompt_capture_enabled():
        return prompt
    return "[REDACTED]"


@contextmanager
def llm_call_span(
    model_name: str,
    prompt: str,
    turn: int = 1,
) -> Generator[Any, None, None]:
    """OpenTelemetry span wrapper for an LLM reasoning call.
    
    Attributes recorded:
    - gen_ai.request.model / model_name
    - turn_number
    - llm.prompt: [REDACTED] unless OTEL_CAPTURE_PROMPTS=true
    - llm.prompt_length: character length
    - llm.prompt_captured: bool
    """
    tracer = telemetry.tracer
    span = tracer.start_span("gen_ai.chat")
    safe_prompt = redact_prompt(prompt)
    try:
        span.set_attribute("gen_ai.request.model", model_name)
        span.set_attribute("model_name", model_name)
        span.set_attribute("turn_number", turn)
        span.set_attribute("llm.prompt", safe_prompt)
        span.set_attribute("llm.prompt_length", len(prompt))
        span.set_attribute("llm.prompt_captured", is_prompt_capture_enabled())
    except Exception:
        pass

    activation = None
    try:
        activation = trace.use_span(span, end_on_exit=False)
        activation.__enter__()
    except Exception:
        activation = None

    try:
        yield span
    except Exception as exc:
        try:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
        except Exception:
            pass
        raise
    finally:
        if activation:
            try:
                activation.__exit__(None, None, None)
            except Exception:
                pass
        try:
            span.end()
        except Exception:
            pass


@contextmanager
def tool_call_child_span(
    tool_name: str,
    arguments: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """OpenTelemetry child span under the active LLM/agent turn for a tool call.
    
    CRITICAL RULE: part_number is ONLY a span attribute, NEVER a metric label.
    """
    tracer = telemetry.tracer
    span = tracer.start_span(f"mcp.tool.{tool_name}")
    try:
        span.set_attribute("tool", tool_name)
        span.set_attribute("tool_name", tool_name)
        span.set_attribute("plm.tool_name", tool_name)

        if arguments:
            identifiers, _ = extract_safe_context((), arguments)
            part_number = identifiers.get("part_number")
            if part_number:
                span.set_attribute("part_number", str(part_number))
                span.set_attribute("plm.id.part_number", str(part_number))

            for k, v in identifiers.items():
                span.set_attribute(f"plm.id.{k}", str(v))
    except Exception:
        pass

    activation = None
    try:
        activation = trace.use_span(span, end_on_exit=False)
        activation.__enter__()
    except Exception:
        activation = None

    try:
        yield span
    except Exception as exc:
        try:
            span.record_exception(exc)
            span.set_status(StatusCode.ERROR, str(exc))
        except Exception:
            pass
        raise
    finally:
        if activation:
            try:
                activation.__exit__(None, None, None)
            except Exception:
                pass
        try:
            span.end()
        except Exception:
            pass


def init_telemetry(
    service_name: str | None = None,
    otlp_endpoint: str | None = None,
    in_memory: bool = False,
) -> None:
    """Initialize telemetry from arguments or environment."""
    telemetry.init(service_name=service_name, otlp_endpoint=otlp_endpoint, in_memory=in_memory)


# =============================================================================
# Payload Sanitization & Identifier/Count Extraction
# =============================================================================

def extract_safe_context(args: tuple, kwargs: dict, result: Any = None) -> tuple[dict[str, Any], dict[str, int]]:
    """Extract strictly safe identifiers and counts without logging secrets or full payloads.
    
    Guarantees:
    - Never logs passwords, tokens, API keys, or credentials.
    - Never logs full BOM tree structures, part descriptions, or CAD payloads.
    - Captures primary identifiers: part_number, version, doc_number, cr_number, serial_number.
    - Captures operational counts: result_count, affected_count, diff_count, etc.
    """
    identifiers: dict[str, Any] = {}
    counts: dict[str, int] = {}

    # 1. Inspect input arguments for safe scalar identifiers
    for k, v in kwargs.items():
        k_lower = k.lower()
        if any(sec in k_lower for sec in SENSITIVE_KEY_SUBSTRINGS):
            continue

        if k_lower in ("part_number", "number", "p_no", "clean_number"):
            if isinstance(v, str):
                identifiers["part_number"] = v
        elif k_lower in ("version", "rev", "iteration"):
            if v is not None:
                identifiers["version"] = str(v)
        elif k_lower in ("doc_number", "defect_number", "serial_number", "cr_number", "cn_number"):
            if isinstance(v, str):
                identifiers[k_lower] = v
        elif k_lower in ("status", "lifecycle_state", "category", "priority"):
            if v is not None:
                identifiers[k_lower] = getattr(v, "value", str(v))
        elif k_lower in ("levels", "depth", "limit", "skip", "page"):
            if isinstance(v, (int, float)):
                identifiers[k_lower] = int(v)
        elif k_lower in ("affected_parts", "parts") and isinstance(v, (list, tuple, set)):
            counts["input_parts_count"] = len(v)
            if v:
                identifiers["sample_part"] = str(list(v)[0])
        elif k_lower in ("a", "b"):  # BOM Compare operands
            if isinstance(v, str):
                identifiers[f"assembly_{k_lower}"] = v
        elif k_lower in ("query", "q") and isinstance(v, str):
            identifiers["query_length"] = len(v)

    # 2. Inspect return payload to record counts ONLY (never full payload structures)
    if result is None:
        counts["result_count"] = 0
    elif isinstance(result, (list, tuple, set)):
        counts["result_count"] = len(result)
    elif hasattr(result, "differences"):
        # BomComparisonResult
        counts["result_count"] = len(result.differences)
        counts["added_count"] = len(getattr(result, "added_parts", []))
        counts["removed_count"] = len(getattr(result, "removed_parts", []))
        counts["modified_count"] = len(getattr(result, "modified_parts", []))
    elif hasattr(result, "all_affected_assemblies"):
        # ChangeImpactAnalysis
        counts["affected_assemblies_count"] = len(result.all_affected_assemblies)
        counts["associated_documents_count"] = len(getattr(result, "associated_documents", []))
        identifiers["impact_level"] = getattr(result, "impact_level", "UNKNOWN")
    elif hasattr(result, "part_number"):
        # Part model instance
        counts["result_count"] = 1
        identifiers["part_number"] = getattr(result, "part_number", "")
        if hasattr(result, "version_label"):
            identifiers["version"] = getattr(result, "version_label", "")
        if hasattr(result, "lifecycle_state"):
            identifiers["lifecycle_state"] = getattr(result.lifecycle_state, "value", str(result.lifecycle_state))
    elif hasattr(result, "cr_number"):
        # ChangeRequest model instance
        counts["result_count"] = 1
        identifiers["cr_number"] = getattr(result, "cr_number", "")
    elif isinstance(result, dict):
        if "error" in result:
            counts["result_count"] = 0
        elif "differences" in result:
            counts["result_count"] = len(result.get("differences", []))
        elif "cr_number" in result:
            counts["result_count"] = 1
            identifiers["cr_number"] = str(result["cr_number"])
        elif "affected_parts" in result:
            counts["affected_parts_count"] = len(result["affected_parts"])
            counts["result_count"] = 1
        else:
            counts["result_count"] = 1
    else:
        counts["result_count"] = 1

    return identifiers, counts


def write_audit_log_entry(
    tool_name: str,
    args: dict[str, Any],
    status: str,
    result_count: int,
    trace_id: str = "",
    span_id: str = "",
    backend: str = "mock",
    duration_ms: float = 0.0,
    identifiers: dict[str, Any] | None = None,
    counts: dict[str, int] | None = None,
    error: Exception | None = None,
) -> None:
    """Record an audit log entry complying with audit test format and OpenTelemetry context."""
    audit_file = "audit.log"
    if "server" in sys.modules and hasattr(sys.modules["server"], "AUDIT_LOG_FILE"):
        audit_file = getattr(sys.modules["server"], "AUDIT_LOG_FILE")
    else:
        audit_file = os.getenv("PLM_AUDIT_LOG_FILE", DEFAULT_AUDIT_LOG_FILE)

    try:
        from validators import redact_sensitive_args
        sanitized_args = redact_sensitive_args(args)
    except Exception:
        sanitized_args = {
            k: v
            for k, v in args.items()
            if not any(sec in k.lower() for sec in SENSITIVE_KEY_SUBSTRINGS)
        }

    entry: dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tool": tool_name,
        "tool_name": tool_name,
        "args": sanitized_args,
        "status": status,
        "result_count": result_count,
        "trace_id": trace_id,
        "span_id": span_id,
        "backend": backend,
        "duration_ms": round(duration_ms, 2),
        "identifiers": identifiers or {},
        "counts": counts or {},
        "error": str(error) if error else None,
    }

    try:
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[AUDIT LOG ERROR] Failed writing to {audit_file}: {e}", file=sys.stderr)


# =============================================================================
# MCP Tool Instrumentation Decorator
# =============================================================================

def instrument_tool(tool_name: str) -> Callable[[F], F]:
    """Decorator for instrumenting FastMCP tools with OpenTelemetry spans, metrics, and JSON logs.
    
    Guarantees:
    - Duration histogram, call counter, error counter, result count recorded.
    - Span with attributes: tool, backend, and part_number ONLY as span attribute (NEVER metric label).
    - Single-line structured JSON logged with trace_id, tool_name, backend, duration_ms, request_id.
    - Fault-tolerance: telemetry failures NEVER break or raise during tool execution.
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            backend_name = os.getenv("PLM_BACKEND", "mock").strip().lower()
            start_time = time.perf_counter()
            tracer = telemetry.tracer

            # Extract arguments
            try:
                sig = inspect.signature(func)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                combined_kwargs = bound.arguments
            except Exception:
                combined_kwargs = dict(kwargs)

            identifiers, _ = extract_safe_context(args, combined_kwargs)
            part_number = identifiers.get("part_number")

            span = None
            span_ctx = None
            trace_id_hex = ""
            span_id_hex = ""

            # Attempt starting span safely
            try:
                span = tracer.start_span(f"mcp.tool.{tool_name}")
                span.set_attribute("tool", tool_name)
                span.set_attribute("tool_name", tool_name)
                span.set_attribute("plm.tool_name", tool_name)
                span.set_attribute("backend", backend_name)
                span.set_attribute("plm.backend", backend_name)
                
                # CRITICAL RULE: part_number ONLY as span attribute, NEVER metric label
                if part_number:
                    span.set_attribute("part_number", str(part_number))

                for id_k, id_v in identifiers.items():
                    span.set_attribute(f"plm.id.{id_k}", str(id_v))

                span_ctx = span.get_span_context()
                if span_ctx and span_ctx.is_valid:
                    trace_id_hex = format_trace_id(span_ctx.trace_id)
                    span_id_hex = format_span_id(span_ctx.span_id)
            except Exception:
                pass

            # Activate span context
            activation = None
            if span:
                try:
                    activation = trace.use_span(span, end_on_exit=False)
                    activation.__enter__()
                except Exception:
                    activation = None

            try:
                result = func(*args, **kwargs)
                duration_sec = time.perf_counter() - start_time
                duration_ms = duration_sec * 1000

                # Extract result counts
                res_ids, res_counts = extract_safe_context(args, combined_kwargs, result)
                res_ids.update(identifiers)
                result_count = res_counts.get("result_count", 0)

                # Update span
                if span:
                    try:
                        span.set_attribute("result_count", result_count)
                        for c_k, c_v in res_counts.items():
                            span.set_attribute(f"plm.count.{c_k}", c_v)
                        span.set_status(StatusCode.OK)
                    except Exception:
                        pass

                # Record metrics: part_number is NEVER in labels
                try:
                    telemetry.record_tool_metrics(
                        tool_name=tool_name,
                        backend=backend_name,
                        status="success",
                        duration_sec=duration_sec,
                        result_count=result_count,
                    )
                except Exception:
                    pass

                # Structured JSON Log
                try:
                    logger.info(
                        f"MCP Tool '{tool_name}' completed successfully in {duration_ms:.2f}ms",
                        extra={
                            "trace_id": trace_id_hex,
                            "span_id": span_id_hex,
                            "tool_name": tool_name,
                            "tool": tool_name,
                            "backend": backend_name,
                            "duration_ms": duration_ms,
                            "status": "SUCCESS",
                            "identifiers": res_ids,
                            "counts": res_counts,
                        },
                    )
                except Exception:
                    pass

                # Audit log file sync
                try:
                    write_audit_log_entry(
                        tool_name=tool_name,
                        args=combined_kwargs,
                        status="SUCCESS",
                        result_count=result_count,
                        trace_id=trace_id_hex,
                        span_id=span_id_hex,
                        backend=backend_name,
                        duration_ms=duration_ms,
                        identifiers=res_ids,
                        counts=res_counts,
                    )
                except Exception:
                    pass

                return result

            except Exception as err:
                duration_sec = time.perf_counter() - start_time
                duration_ms = duration_sec * 1000

                if span:
                    try:
                        span.record_exception(err)
                        span.set_status(StatusCode.ERROR, str(err))
                    except Exception:
                        pass

                # Record error metric
                try:
                    telemetry.record_tool_metrics(
                        tool_name=tool_name,
                        backend=backend_name,
                        status="error",
                        duration_sec=duration_sec,
                        result_count=0,
                    )
                except Exception:
                    pass

                try:
                    logger.error(
                        f"MCP Tool '{tool_name}' failed after {duration_ms:.2f}ms: {err}",
                        extra={
                            "trace_id": trace_id_hex,
                            "span_id": span_id_hex,
                            "tool_name": tool_name,
                            "tool": tool_name,
                            "backend": backend_name,
                            "duration_ms": duration_ms,
                            "status": "ERROR",
                            "identifiers": identifiers,
                            "error": str(err),
                        },
                    )
                except Exception:
                    pass

                try:
                    write_audit_log_entry(
                        tool_name=tool_name,
                        args=combined_kwargs,
                        status="ERROR",
                        result_count=0,
                        trace_id=trace_id_hex,
                        span_id=span_id_hex,
                        backend=backend_name,
                        duration_ms=duration_ms,
                        identifiers=identifiers,
                        error=err,
                    )
                except Exception:
                    pass

                raise

            finally:
                if activation:
                    try:
                        activation.__exit__(None, None, None)
                    except Exception:
                        pass
                if span:
                    try:
                        span.end()
                    except Exception:
                        pass

        return wrapper  # type: ignore

    return decorator


# =============================================================================
# PLMBackend Instrumentation & Wrapper
# =============================================================================

def instrument_backend_method(method_name: str, backend_name_override: str | None = None) -> Callable[[F], F]:
    """Decorator instrumenting a PLMBackend method with OpenTelemetry metrics and child span."""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            backend_name = backend_name_override
            if not backend_name and args:
                first_arg = args[0]
                if hasattr(first_arg, "backend_name"):
                    backend_name = getattr(first_arg, "backend_name")
                elif hasattr(first_arg, "__class__"):
                    cls_name = first_arg.__class__.__name__
                    if "Mock" in cls_name:
                        backend_name = "mock"
                    elif "Windchill" in cls_name:
                        backend_name = "windchill"

            if not backend_name:
                backend_name = os.getenv("PLM_BACKEND", "mock").strip().lower()

            start_time = time.perf_counter()
            tracer = telemetry.tracer

            try:
                sig = inspect.signature(func)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                combined_kwargs = {k: v for k, v in bound.arguments.items() if k not in ("self", "cls")}
            except Exception:
                combined_kwargs = dict(kwargs)

            identifiers, _ = extract_safe_context(args, combined_kwargs)
            part_number = identifiers.get("part_number")

            span = None
            activation = None
            trace_id_hex = ""
            span_id_hex = ""

            try:
                span = tracer.start_span(f"PLMBackend.{method_name}")
                span.set_attribute("method", method_name)
                span.set_attribute("tool", method_name)
                span.set_attribute("tool_name", method_name)
                span.set_attribute("plm.method_name", method_name)
                span.set_attribute("backend", backend_name)
                span.set_attribute("plm.backend", backend_name)

                # CRITICAL RULE: part_number ONLY as span attribute, NEVER metric label
                if part_number:
                    span.set_attribute("part_number", str(part_number))

                for id_k, id_v in identifiers.items():
                    span.set_attribute(f"plm.id.{id_k}", str(id_v))

                span_ctx = span.get_span_context()
                if span_ctx and span_ctx.is_valid:
                    trace_id_hex = format_trace_id(span_ctx.trace_id)
                    span_id_hex = format_span_id(span_ctx.span_id)

                activation = trace.use_span(span, end_on_exit=False)
                activation.__enter__()
            except Exception:
                span = None
                activation = None

            try:
                result = func(*args, **kwargs)
                duration_sec = time.perf_counter() - start_time
                duration_ms = duration_sec * 1000

                res_ids, res_counts = extract_safe_context(args, combined_kwargs, result)
                res_ids.update(identifiers)
                result_count = res_counts.get("result_count", 0)

                if span:
                    try:
                        span.set_attribute("result_count", result_count)
                        for c_k, c_v in res_counts.items():
                            span.set_attribute(f"plm.count.{c_k}", c_v)
                        span.set_status(StatusCode.OK)
                    except Exception:
                        pass

                # Record metrics: part_number NEVER in labels
                try:
                    telemetry.record_backend_metrics(
                        method_name=method_name,
                        backend=backend_name,
                        status="success",
                        duration_sec=duration_sec,
                        result_count=result_count,
                    )
                except Exception:
                    pass

                try:
                    logger.info(
                        f"PLMBackend.{method_name} executed in {duration_ms:.2f}ms",
                        extra={
                            "trace_id": trace_id_hex,
                            "span_id": span_id_hex,
                            "tool_name": f"PLMBackend.{method_name}",
                            "tool": method_name,
                            "backend": backend_name,
                            "duration_ms": duration_ms,
                            "status": "SUCCESS",
                            "identifiers": res_ids,
                            "counts": res_counts,
                        },
                    )
                except Exception:
                    pass

                return result

            except Exception as err:
                duration_sec = time.perf_counter() - start_time
                duration_ms = duration_sec * 1000

                if span:
                    try:
                        span.record_exception(err)
                        span.set_status(StatusCode.ERROR, str(err))
                    except Exception:
                        pass

                try:
                    telemetry.record_backend_metrics(
                        method_name=method_name,
                        backend=backend_name,
                        status="error",
                        duration_sec=duration_sec,
                        result_count=0,
                    )
                except Exception:
                    pass

                try:
                    logger.error(
                        f"PLMBackend.{method_name} failed after {duration_ms:.2f}ms: {err}",
                        extra={
                            "trace_id": trace_id_hex,
                            "span_id": span_id_hex,
                            "tool_name": f"PLMBackend.{method_name}",
                            "tool": method_name,
                            "backend": backend_name,
                            "duration_ms": duration_ms,
                            "status": "ERROR",
                            "identifiers": identifiers,
                            "error": str(err),
                        },
                    )
                except Exception:
                    pass

                raise

            finally:
                if activation:
                    try:
                        activation.__exit__(None, None, None)
                    except Exception:
                        pass
                if span:
                    try:
                        span.end()
                    except Exception:
                        pass

        return wrapper  # type: ignore

    return decorator


def instrument_all_backend_methods(cls: type) -> type:
    """Class post-processor that instruments all public methods on a PLMBackend implementation."""
    for attr_name, attr_val in list(cls.__dict__.items()):
        if not attr_name.startswith("_") and callable(attr_val) and not isinstance(attr_val, (staticmethod, classmethod)):
            if not getattr(attr_val, "__is_instrumented__", False):
                wrapped = instrument_backend_method(attr_name)(attr_val)
                wrapped.__is_instrumented__ = True  # type: ignore
                setattr(cls, attr_name, wrapped)
    return cls


class InstrumentedPLMBackend:
    """Explicit wrapper around any PLMBackend instance providing full OpenTelemetry instrumentation."""

    def __init__(self, backend: Any) -> None:
        self._backend = backend
        self.backend_name = getattr(backend, "backend_name", None) or ("mock" if "Mock" in backend.__class__.__name__ else "windchill")

    def __getattr__(self, name: str) -> Any:
        attr = getattr(self._backend, name)
        if callable(attr) and not name.startswith("_"):
            wrapped = instrument_backend_method(name, backend_name_override=self.backend_name)(attr)
            return wrapped
        return attr


# =============================================================================
# Cross-Domain Adapter Instrumentation (ERP, QMS, IIoT)
# =============================================================================

def instrument_adapter_method(adapter_name: str, method_name: str) -> Callable[[F], F]:
    """Instruments an adapter method (ERP, QMS, IIoT) creating a child span under the active trace."""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            tracer = telemetry.tracer
            try:
                sig = inspect.signature(func)
                bound = sig.bind(self, *args, **kwargs)
                bound.apply_defaults()
                combined_kwargs = {k: v for k, v in bound.arguments.items() if k != "self"}
            except Exception:
                combined_kwargs = dict(kwargs)

            identifiers, _ = extract_safe_context(args, combined_kwargs)
            part_number = identifiers.get("part_number")

            span = None
            activation = None
            try:
                span = tracer.start_span(f"{adapter_name}.{method_name}")
                span.set_attribute("adapter", adapter_name)
                span.set_attribute("method", method_name)
                if part_number:
                    span.set_attribute("part_number", str(part_number))
                for id_k, id_v in identifiers.items():
                    span.set_attribute(f"plm.id.{id_k}", str(id_v))
                activation = trace.use_span(span, end_on_exit=False)
                activation.__enter__()
            except Exception:
                span = None
                activation = None

            try:
                result = func(self, *args, **kwargs)
                if span:
                    span.set_status(StatusCode.OK)
                return result
            except Exception as err:
                if span:
                    span.record_exception(err)
                    span.set_status(StatusCode.ERROR, str(err))
                raise
            finally:
                if activation:
                    try:
                        activation.__exit__(None, None, None)
                    except Exception:
                        pass
                if span:
                    try:
                        span.end()
                    except Exception:
                        pass
        return wrapper  # type: ignore
    return decorator


def instrument_all_adapter_methods(adapter_name: str, cls: type) -> type:
    """Class post-processor that instruments all public methods on an adapter."""
    for attr_name, attr_val in list(cls.__dict__.items()):
        if not attr_name.startswith("_") and callable(attr_val) and not isinstance(attr_val, (staticmethod, classmethod)):
            if not getattr(attr_val, "__is_instrumented__", False):
                wrapped = instrument_adapter_method(adapter_name, attr_name)(attr_val)
                wrapped.__is_instrumented__ = True  # type: ignore
                setattr(cls, attr_name, wrapped)
    return cls


# =============================================================================
# Custom FastAPI Middleware for Request ID & Trace Correlation
# =============================================================================

class RequestIDMiddleware(BaseHTTPMiddleware):
    """Custom middleware that extracts or generates a Request ID (X-Request-ID).
    
    Functions:
    - Extracts 'X-Request-ID' from incoming request or generates a new UUID.
    - Attaches request_id to request.state and contextvars for log formatting.
    - Sets 'http.request_id' and 'request_id' on active OpenTelemetry span.
    - Injects 'X-Request-ID' into the HTTP response headers.
    """

    async def dispatch(self, request: Request, call_next: Callable[[Request], Any]) -> Response:
        req_id = (
            request.headers.get("X-Request-ID")
            or request.headers.get("X-Request-Id")
            or str(uuid.uuid4())
        )
        request.state.request_id = req_id
        token = request_id_ctx.set(req_id)

        # Correlate with active OpenTelemetry span if available
        try:
            current_span = trace.get_current_span()
            if current_span and current_span.is_recording():
                current_span.set_attribute("http.request_id", req_id)
                current_span.set_attribute("request_id", req_id)
        except Exception:
            pass

        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = req_id
            return response
        finally:
            request_id_ctx.reset(token)
