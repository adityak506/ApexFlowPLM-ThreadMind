# Mock PLM (Windchill-Style) MCP Server

A Product Lifecycle Management (PLM) system inspired by PTC Windchill core semantics, exposed as a Model Context Protocol (MCP) server using the official Python FastMCP SDK.

## Key Features

- **Windchill Semantic Integrity**:
  - **Parts & Versioning**: Separation of Part Master identity and Revision/Iteration instances (e.g. `A.1` $\rightarrow$ `A.2` while `IN_WORK`; promoting to `RELEASED`; revising to `B.1`).
  - **Lifecycle States**: Enforces standard Windchill state machine (`IN_WORK` $\rightarrow$ `UNDER_REVIEW` $\rightarrow$ `RELEASED` $\rightarrow$ `OBSOLETE`).
  - **Bill of Materials (BOM)**: Single-level and multi-level recursive indented BOM explosions with quantities, units, line find numbers, and reference designators.
  - **Where-Used Analysis**: Trace which parent assemblies consume specific component parts.
  - **Documents (`WTDocument`)**: Specifications, CAD drawings, test reports, and user manuals with simulated vault attachments and `DESCRIBES` / `REFERENCES` part associations.
  - **Change Management**: Engineering Change Requests (ECR) linked to Engineering Change Notices (ECN), tracking affected items with material dispositions (`SCRAP`, `REWORK`, `USE_AS_IS`).
  - **Supplier & AML/AVL**: Approved Manufacturer List tracking internal parts to external manufacturer catalog items with sourcing statuses (`PREFERRED`, `APPROVED`, `DO_NOT_USE`).
- **Adapter Architecture**: All MCP tools interact strictly with the abstract `PLMBackend` interface.
  - `MockBackend`: High-performance SQLite implementation seeded with a realistic Autonomous Quadcopter Drone assembly.
  - `WindchillBackend`: Enterprise stub for PTC Windchill REST Services (WRS) / OData APIs (all endpoints marked with `TODO: verify against Windchill docs`).
- **Safety by Default**: Every mutation tool requires explicit `confirm=True` to persist changes. By default (`confirm=False`), tools execute in **dry-run / draft mode** returning a structured change preview.

---

## Architecture Overview

```
                      +-----------------------------+
                      |   LLM / Agent (FastMCP)     |
                      +--------------+--------------+
                                     |
                          [Tool Registry & Safety]
                                     |
                      +--------------v--------------+
                      |     <<PLMBackend>>          |
                      |   (Abstract Interface)      |
                      +-------+--------------+------+
                              |              |
           PLM_BACKEND=mock   |              |  PLM_BACKEND=windchill
                              v              v
                  +-------------------+  +--------------------+
                  |   MockBackend     |  |  WindchillBackend  |
                  |     (SQLite)      |  |  (REST/OData Stub) |
                  +-------------------+  +--------------------+
```

---

## Quickstart & Installation

### 1. Requirements
- Python 3.11+
- Virtual environment (recommended)

### 2. Setup
```bash
# Clone and enter workspace
git clone <repo-url>
cd CapstoneProject

# Create and activate virtual environment
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# Install package and dependencies
pip install -e .
```

### 3. Run the Server
```bash
# Run standalone server with stdio transport
python server.py

# Test interactively with MCP Inspector
npx @modelcontextprotocol/inspector python server.py
```

---

## MCP Client Configuration

### Claude Desktop (`claude_desktop_config.json`)
```json
{
  "mcpServers": {
    "plm": {
      "command": "python",
      "args": ["-m", "plm_mcp"],
      "cwd": "/path/to/CapstoneProject",
      "env": {
        "PLM_BACKEND": "mock",
        "PLM_SQLITE_PATH": "plm_mock.db",
        "PLM_SEED_ON_STARTUP": "true"
      }
    }
  }
}
```

### Antigravity / Cursor Configuration
```json
{
  "mcpServers": {
    "mock-plm": {
      "command": "python",
      "args": ["-m", "plm_mcp"]
    }
  }
}
```

---

## Environment Variables

| Variable | Default | Description |
| :--- | :--- | :--- |
| `PLM_BACKEND` | `mock` | Active backend adapter: `mock` (SQLite) or `windchill` (OData). |
| `PLM_SQLITE_PATH` | `plm_mock.db` | Path to SQLite database file, or `:memory:` for ephemeral memory store. |
| `PLM_SEED_ON_STARTUP` | `true` | Automatically populate realistic Quadcopter Drone seed dataset if empty. |
| `WINDCHILL_BASE_URL` | `""` | Base URL for PTC Windchill instance (when `PLM_BACKEND=windchill`). |
| `WINDCHILL_USERNAME` | `""` | Windchill service account username. |
| `WINDCHILL_PASSWORD` | `""` | Windchill service account password. |
| `WINDCHILL_CONTAINER` | `"Demo Product"` | Target Windchill Product Context. |

---

## MCP Tools Reference

### Part Management
- **`get_part(part_number, version=None)`**: Get part details, lifecycle state, and association counts.
- **`search_parts(query, lifecycle_state=None, limit=20)`**: Search parts across numbers, names, and descriptions.
- **`create_part(part_number, name, description="", confirm=False)`**: Initialize a new part at `A.1` in `IN_WORK`.
- **`iterate_part(part_number, description="", confirm=False)`**: Increment iteration (e.g. `A.1` $\rightarrow$ `A.2`) on an `IN_WORK` part.
- **`revise_part(part_number, description="", confirm=False)`**: Revise a `RELEASED` part to next revision (e.g. `A.2` $\rightarrow$ `B.1`).
- **`set_part_lifecycle_state(part_number, target_state, confirm=False)`**: Promote state (`IN_WORK` $\rightarrow$ `UNDER_REVIEW` $\rightarrow$ `RELEASED` $\rightarrow$ `OBSOLETE`).

### Bill of Materials (BOM)
- **`get_part_bom(part_number, levels=1, version=None)`**: Indented BOM tree explosion.
- **`get_where_used(part_number, top_level_only=False)`**: Query parent assemblies consuming this part.
- **`add_bom_component(parent_part_number, child_part_number, quantity, unit="ea", find_number=None, ref_designators=None, notes="", confirm=False)`**: Add usage link.
- **`remove_bom_component(parent_part_number, child_part_number, confirm=False)`**: Remove usage link.

### Document Management
- **`get_document(doc_number, version=None)`**: Retrieve document metadata and simulated attachments.
- **`search_documents(query, doc_type=None, limit=20)`**: Search specifications, drawings, and reports.
- **`create_document(doc_number, name, doc_type="SPECIFICATION", file_name=None, confirm=False)`**: Create document at `A.1`.
- **`link_document_to_part(part_number, doc_number, link_type="DESCRIBES", confirm=False)`**: Link document to part.

### Change Management (ECR & ECN)
- **`create_change_request(title, description, category, priority, affected_parts=[], confirm=False)`**: File an ECR.
- **`get_change_request(cr_number)`**: Retrieve ECR status and affected parts.
- **`create_change_notice(title, description, cr_number=None, confirm=False)`**: Create an ECN.
- **`get_change_notice(cn_number)`**: Retrieve ECN with affected and resulting items.
- **`add_change_affected_item(cn_number, item_type, item_number, disposition="USE_AS_IS", confirm=False)`**: Attach affected items with scrap/rework directives.
- **`execute_change_notice(cn_number, confirm=False)`**: Finalize ECN and disposition parts.

### Supplier & Sourcing (AML/AVL)
- **`search_manufacturers(query, status=None)`**: Search registered vendors and CAGE codes.
- **`get_part_aml(part_number)`**: Retrieve Approved Manufacturer List with preference ranks.
- **`add_manufacturer(name, cage_code=None, country="USA", confirm=False)`**: Register external vendor.
- **`add_manufacturer_part(mfr_name, mfr_part_number, description="", confirm=False)`**: Register catalog part.
- **`set_sourcing_link(part_number, mfr_name, mfr_part_number, status="APPROVED", preference_rank=1, confirm=False)`**: Link manufacturer part to internal part.

---

## Running the REST API & Web UI Together

The mock PLM solution includes a FastAPI backend (`api.py`) exposing 13 REST endpoints that wrap the `PLMBackend`, and a React + TypeScript + Vite web interface (`ui/`) featuring 9 interactive governance screens, AI Assistant integration, and Playwright end-to-end tests.

### 1. Start the FastAPI Backend
In the repository root directory:
```bash
# Ensure Python virtual environment is active
python -m uvicorn api:app --host 127.0.0.1 --port 8000
```
* **API URL**: `http://127.0.0.1:8000`
* **Interactive OpenAPI Swagger Docs**: `http://127.0.0.1:8000/docs`

### 2. Start the React Frontend Dev Server
In a separate terminal window:
```bash
cd ui
npm install
npm run dev
```
* **Web UI URL**: `http://127.0.0.1:5173`

### 3. Automated Test Suites
Both suites can be executed independently:

```bash
# Backend, REST API, Security & Observability Test Suite (154 tests)
pytest -v

# Playwright Browser End-to-End Test Suite (5 core flows)
npm --prefix ui run test:e2e
```

---

## OpenTelemetry Observability

The mock PLM server and backend are instrumented with vendor-neutral **OpenTelemetry** for distributed tracing, metrics, and structured JSON logging.

### Observability Standards & Guarantees
1. **Vendor-Neutral OpenTelemetry**: Native OpenTelemetry SDK implementation (`TracerProvider`, `MeterProvider`, standard OTLP HTTP/gRPC exporter) with no vendor locks or proprietary dependencies.
2. **Structured JSON Logs**: Emits single-line JSON logs to `observability.log` and `audit.log` containing `trace_id`, `span_id`, `tool_name`, `backend`, `duration_ms`, `status`, `identifiers`, and `counts`.
3. **Strict Data Protection**: Credentials (`password`, `token`, `secret`, `api_key`, `auth`) are scrubbed before logging. Full part/BOM payloads or CAD files are never logged; operations record high-level counts and primary identifiers only.
4. **Complete Instrumentation**: All 15 FastMCP tools and all `PLMBackend` methods are instrumented. Sub-calls to `PLMBackend` automatically create child spans inheriting the MCP tool's `trace_id`.
5. **Collector Fault-Tolerance**: Configurable via `OTEL_EXPORTER_OTLP_ENDPOINT` and `OTEL_SERVICE_NAME`. Network timeouts or unreachable OTLP collectors log a local warning and **never crash or halt the server process**.

### Environment Configuration
| Variable | Description | Default |
|---|---|---|
| `OTEL_SERVICE_NAME` | Service name tag attached to all traces and metrics | `mock-plm-server` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | OTLP Collector endpoint (HTTP port 4318 or gRPC port 4317) | *(none - local tracing)* |
| `PLM_LOG_FILE` | Structured JSON application log destination | `observability.log` |
| `PLM_AUDIT_LOG_FILE` | Dedicated audit log destination | `audit.log` |

### Sample Structured JSON Log Record
```json
{
  "timestamp": "2026-11-07T14:45:51.304236Z",
  "level": "INFO",
  "message": "MCP Tool 'get_part' completed successfully in 21.57ms",
  "trace_id": "15ff6a01bd0eb7890887a962bcce86bf",
  "span_id": "8fc5e0d073427c01",
  "tool_name": "get_part",
  "backend": "mock",
  "duration_ms": 21.57,
  "status": "SUCCESS",
  "identifiers": {"part_number": "PMP-0001", "version": "B.1", "lifecycle_state": "RELEASED"},
  "counts": {"result_count": 1}
}
```

---

## Observability Infrastructure Stack (Docker Compose)

The `/observability` directory provides a fully integrated, production-grade observability stack containing:
- **OpenTelemetry Collector (Contrib)**: Unified ingestion pipeline for traces, metrics, and logs via OTLP.
- **Prometheus**: Time-series metrics engine scraping the OTel Collector.
- **Grafana Tempo**: Distributed tracing engine for end-to-end trace correlation.
- **Grafana Loki**: Log aggregation engine for structured JSON telemetry.
- **Grafana**: Pre-provisioned dashboards and datasources.

### 1. One-Command Startup
```bash
# Start all 5 observability services in the background:
make obs-up
# Alternatively using docker compose directly:
docker compose -f observability/docker-compose.yml up -d

# Stop all observability services:
make obs-down
# Or:
docker compose -f observability/docker-compose.yml down
```

### 2. Exposed Service Ports & Endpoints
| Service | Port | Protocol | Purpose / Access URL |
|---|---|---|---|
| **OTel Collector** | `4317` | gRPC | OTLP telemetry receiver (`grpc://localhost:4317`) |
| **OTel Collector** | `4318` | HTTP | OTLP HTTP receiver (`http://localhost:4318`) |
| **OTel Collector** | `8889` | HTTP | Prometheus metrics bridge endpoint (`http://localhost:8889/metrics`) |
| **OTel Collector** | `13133` | HTTP | Collector health check endpoint (`http://localhost:13133`) |
| **Prometheus** | `9090` | HTTP | Prometheus UI & Query Engine (`http://localhost:9090`) |
| **Grafana Tempo** | `3200` | HTTP | Tempo query & trace search API (`http://localhost:3200`) |
| **Grafana Loki** | `3100` | HTTP | Loki log push/query API (`http://localhost:3100`) |
| **Grafana UI** | `3000` | HTTP | Web UI (`http://localhost:3000`, User: `admin` / Password: `admin`) |

### 3. Provisioned Grafana Dashboards
Located in `/observability/grafana/provisioning/dashboards/`:
1. **API Health** (`dashboard_1_api_health.json`): Request throughput rate, p95 latency by route, error rate %.
2. **MCP Tools** (`dashboard_2_mcp_tools.json`): Call counters, p95 latency, error counters per tool, and ranking of slowest tools.
3. **PLM Backend** (`dashboard_3_plm_backend.json`): Backend method latency and side-by-side **Mock vs. Windchill** comparison panel.
4. **AI Agent** (`dashboard_4_ai_agent.json`): Tokens in vs. out, estimated USD cost, tool calls per conversation, agent reasoning turns, and rejected draft count.
5. **Business KPIs** (`dashboard_5_business.json`): Issues detected by type, blast-radius impact analyses run, and ECR funnel (drafted vs. confirmed vs. rejected).

### 4. Prometheus Alert Rules
Defined in `/observability/alert_rules.yml`:
- **HighAPIErrorRate**: Triggers when API/Backend error rate exceeds 5% for more than 5 minutes (`severity: critical`).
- **HighToolLatency**: Triggers when MCP tool p95 execution latency exceeds 2 seconds for 2 minutes (`severity: warning`).
- **HighBackendErrors**: Triggers when backend errors exceed 0.5 errors/second for 1 minute (`severity: critical`).
- **HighLLMCostPerHour**: Triggers when estimated LLM inference expenditure exceeds $10.00/hour for 5 minutes (`severity: warning`).

---

## Running the Automated Test Suite

```bash
# Run all unit and integration tests
pytest -v
```

