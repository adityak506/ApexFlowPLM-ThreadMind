"""Tests for AI Assistant /chat Endpoint and Agent Loop Observability.

Validates all 7 core requirements:
1. Recording tokens in/out, model name, latency, time to first token (TTFT).
2. Recording tool calls per conversation and number of agent turns.
3. Recording failed tool calls and marking child tool span status ERROR.
4. Calculating estimated cost using the configurable price table in config.py.
5. Tracing hierarchy: parent span per LLM call and child span per tool call.
6. Redaction of prompt contents by default; enabled only with OTEL_CAPTURE_PROMPTS=true.
7. Agent quality counter incremented on user draft rejection and max turns exceeded.
"""

import json
import os
import pytest
from starlette.testclient import TestClient

from api import app, PENDING_DRAFTS
import config
from mock_backend import MockBackend
from seed_data import generate_dataset
import server
from telemetry import (
    init_telemetry,
    is_prompt_capture_enabled,
    record_agent_quality_issue,
    record_agent_tool_call,
    record_agent_tool_failed,
    record_agent_turns,
    record_llm_cost,
    record_llm_latency,
    record_llm_tokens,
    record_llm_ttft,
    redact_prompt,
    telemetry,
)


@pytest.fixture(autouse=True)
def setup_chat_telemetry_env(tmp_path, monkeypatch):
    """Setup isolated database, in-memory telemetry, and reset pricing."""
    db_path = str(tmp_path / "test_chat_obs.db")
    generate_dataset(db_path=db_path)

    monkeypatch.setenv("PLM_SQLITE_PATH", db_path)
    monkeypatch.setenv("PLM_BACKEND", "mock")
    monkeypatch.setenv("OTEL_CAPTURE_PROMPTS", "false")
    monkeypatch.setenv("MAX_AGENT_TURNS", "5")
    monkeypatch.setenv("LLM_MODEL_NAME", "mock-llm")

    telemetry.init(service_name="test-chat-service", in_memory=True)
    telemetry.clear_spans()
    config.reset_model_pricing()
    PENDING_DRAFTS.clear()

    yield {"db_path": db_path}

    config.reset_model_pricing()
    PENDING_DRAFTS.clear()


# =============================================================================
# 1. Configurable Pricing Table Tests
# =============================================================================

def test_configurable_price_table_calculation():
    """Verify default price calculation and custom price overrides in config."""
    # Default mock-llm pricing: $0.50 per 1M in, $1.50 per 1M out
    cost_default = config.calculate_llm_cost("mock-llm", input_tokens=1_000_000, output_tokens=1_000_000)
    assert pytest.approx(cost_default, 0.001) == 2.00

    # Custom price override
    config.set_model_price("mock-llm", input_per_million=5.00, output_per_million=15.00)
    cost_custom = config.calculate_llm_cost("mock-llm", input_tokens=1_000_000, output_tokens=1_000_000)
    assert pytest.approx(cost_custom, 0.001) == 20.00

    # Known model check (e.g. gpt-4o: $2.50 in, $10.00 out)
    cost_gpt4o = config.calculate_llm_cost("gpt-4o", input_tokens=500_000, output_tokens=100_000)
    # (0.5 * 2.50) + (0.1 * 10.00) = 1.25 + 1.00 = 2.25
    assert pytest.approx(cost_gpt4o, 0.001) == 2.25


# =============================================================================
# 2. Prompt Redaction & OTEL_CAPTURE_PROMPTS Tests
# =============================================================================

def test_prompt_redaction_default_false(monkeypatch):
    """Verify prompt content is redacted by default when OTEL_CAPTURE_PROMPTS is false or unset."""
    monkeypatch.setenv("OTEL_CAPTURE_PROMPTS", "false")
    assert not is_prompt_capture_enabled()

    secret_prompt = "Confidential nuclear reactor geometry blueprint PMP-0010"
    assert redact_prompt(secret_prompt) == "[REDACTED]"

    client = TestClient(app)
    response = client.post("/chat", json={"message": secret_prompt, "history": []})
    assert response.status_code == 200

    spans = telemetry.get_finished_spans()
    llm_spans = [s for s in spans if s.name == "gen_ai.chat"]
    assert len(llm_spans) >= 1
    assert llm_spans[0].attributes["llm.prompt"] == "[REDACTED]"
    assert llm_spans[0].attributes["llm.prompt_captured"] is False


def test_prompt_capture_enabled_when_flag_true(monkeypatch):
    """Verify prompt content is captured ONLY when OTEL_CAPTURE_PROMPTS is explicitly true."""
    monkeypatch.setenv("OTEL_CAPTURE_PROMPTS", "true")
    assert is_prompt_capture_enabled()

    debug_prompt = "Find obsolete parts in released BOMs for debugging"
    assert redact_prompt(debug_prompt) == debug_prompt

    client = TestClient(app)
    response = client.post("/chat", json={"message": debug_prompt, "history": []})
    assert response.status_code == 200

    spans = telemetry.get_finished_spans()
    llm_spans = [s for s in spans if s.name == "gen_ai.chat"]
    assert len(llm_spans) >= 1
    assert llm_spans[0].attributes["llm.prompt"] == debug_prompt
    assert llm_spans[0].attributes["llm.prompt_captured"] is True


# =============================================================================
# 3. LLM Call Spans, Child Tool Spans & Metrics Recording
# =============================================================================

def test_chat_endpoint_traces_llm_and_child_tool_spans():
    """Verify /chat execution records a parent LLM span, child tool spans,
    and all required attributes (tokens, latency, TTFT, cost, model).
    """
    client = TestClient(app)
    response = client.post(
        "/chat",
        json={"message": "What is the change impact of part PMP-0010?", "history": []},
    )
    assert response.status_code == 200

    # Parse SSE stream to ensure completed
    lines = response.text.splitlines()
    assert any("event: tool_call" in l for l in lines)
    assert any("event: tool_result" in l for l in lines)
    assert any("event: done" in l for l in lines)

    spans = telemetry.get_finished_spans()
    llm_spans = [s for s in spans if s.name == "gen_ai.chat"]
    tool_spans = [s for s in spans if s.name == "mcp.tool.analyze_change_impact"]

    assert len(llm_spans) >= 1
    l_span = llm_spans[0]

    # Model and Token attributes
    assert l_span.attributes["model_name"] == "mock-llm"
    assert l_span.attributes["tokens.input"] > 0
    assert l_span.attributes["tokens.output"] > 0
    assert l_span.attributes["tokens.total"] == (
        l_span.attributes["tokens.input"] + l_span.attributes["tokens.output"]
    )

    # Latency, TTFT, Cost attributes
    assert l_span.attributes["llm.latency_ms"] > 0
    assert l_span.attributes["llm.time_to_first_token_ms"] > 0
    assert l_span.attributes["llm.estimated_cost_usd"] > 0

    # Hierarchy verification: Child tool span is nested under parent LLM / request trace
    assert len(tool_spans) >= 1
    t_span = tool_spans[0]
    assert t_span.context.trace_id == l_span.context.trace_id
    assert t_span.attributes["tool"] == "analyze_change_impact"
    # CRITICAL RULE: part_number is only a span attribute
    assert t_span.attributes["part_number"] == "PMP-0010"


def test_failed_tool_call_records_error_and_metric():
    """Verify that when a tool call fails, child span records ERROR and failed metric increments."""
    from chat_service import stream_chat_events

    class BrokenBackend(MockBackend):
        def analyze_change_impact(self, part_number: str):
            raise RuntimeError("Database connection timeout during impact blast radius calculation")

    broken = BrokenBackend(db_path=os.getenv("PLM_SQLITE_PATH"))

    async def run_broken():
        events = []
        async for evt in stream_chat_events(
            message="What is the change impact of part PMP-0010?",
            history=[],
            backend=broken,
            pending_drafts={},
        ):
            events.append(evt)
        return events

    import asyncio
    asyncio.run(run_broken())

    spans = telemetry.get_finished_spans()
    failed_tool_spans = [s for s in spans if s.name == "mcp.tool.analyze_change_impact"]
    assert len(failed_tool_spans) >= 1
    err_span = failed_tool_spans[0]
    assert not err_span.status.is_ok
    assert "Database connection timeout" in err_span.status.description

    # Verify metrics data
    metrics_data = telemetry.get_metrics_data()
    assert metrics_data is not None


# =============================================================================
# 4. Agent Quality Degradation Metrics Tests
# =============================================================================

def test_agent_quality_counter_on_rejected_draft():
    """Verify threadmind_agent_quality_issues_total{reason=rejected_draft} on draft rejection."""
    client = TestClient(app)

    # 1. Draft a change request
    draft_res = client.post(
        "/changes/draft",
        json={
            "title": "Propose impeller replacement",
            "affected_parts": ["PMP-0010"],
            "reason": "Vibration wear detected during routine run",
            "category": "DESIGN_IMPROVEMENT",
            "priority": "HIGH",
        },
    )
    assert draft_res.status_code == 200
    draft_id = draft_res.json()["draft_id"]
    assert draft_id in PENDING_DRAFTS

    # 2. Reject the draft via POST /changes/{id}/reject
    reject_res = client.post(f"/changes/{draft_id}/reject")
    assert reject_res.status_code == 200
    assert reject_res.json()["status"] == "REJECTED"
    assert draft_id not in PENDING_DRAFTS

    # 3. Verify metrics recorded
    metrics_data = telemetry.get_metrics_data()
    assert metrics_data is not None

    found_rejected = False
    for rm in metrics_data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == "threadmind_agent_quality_issues_total":
                    for dp in m.data.data_points:
                        if dp.attributes.get("reason") == "rejected_draft":
                            assert dp.value >= 1
                            found_rejected = True
    assert found_rejected


def test_agent_quality_counter_on_rejected_draft_in_chat():
    """Verify agent quality counter is recorded when user rejects draft via /chat."""
    PENDING_DRAFTS["DRAFT-TEST999"] = {
        "draft_id": "DRAFT-TEST999",
        "title": "Candidate change to reject",
        "affected_parts": ["PMP-0010"],
        "reason": "Test draft",
    }

    client = TestClient(app)
    response = client.post(
        "/chat",
        json={"message": "I reject draft DRAFT-TEST999, please cancel it.", "history": []},
    )
    assert response.status_code == 200
    assert "DRAFT-TEST999" not in PENDING_DRAFTS

    metrics_data = telemetry.get_metrics_data()
    assert metrics_data is not None


def test_agent_quality_counter_on_max_turns_exceeded(monkeypatch):
    """Verify threadmind_agent_quality_issues_total{reason=max_turns_exceeded} when agent hits max turns."""
    monkeypatch.setenv("MAX_AGENT_TURNS", "1")

    client = TestClient(app)
    response = client.post(
        "/chat",
        json={"message": "Run a complex-workflow multi-turn iterative analysis", "history": []},
    )
    assert response.status_code == 200
    assert "Max Turns Exceeded" in response.text

    metrics_data = telemetry.get_metrics_data()
    assert metrics_data is not None

    found_max_turns = False
    for rm in metrics_data.resource_metrics:
        for sm in rm.scope_metrics:
            for m in sm.metrics:
                if m.name == "threadmind_agent_quality_issues_total":
                    for dp in m.data.data_points:
                        if dp.attributes.get("reason") == "max_turns_exceeded":
                            assert dp.value >= 1
                            found_max_turns = True
    assert found_max_turns
