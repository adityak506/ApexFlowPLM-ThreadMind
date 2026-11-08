"""ThreadMind PLM Load Testing Script (Locust)

Simulates realistic multi-persona traffic against the Mock PLM REST API:
1. PartCatalogUser (weight=35): Parts search, filtering, and component details
2. BomExplorerUser (weight=25): Multi-level BOM hierarchy retrieval, where-used tree, and BOM comparisons
3. ImpactAnalysisUser (weight=15): Blast-radius and change impact assessments
4. AiAssistantChatUser (weight=15): LLM chat completions with PLM MCP tool invocation
5. ClosedLoopScenarioUser (weight=10): Full digital thread closed-loop lifecycle:
   IIoT sensor anomaly -> QMS defect -> PLM impact -> ERP inventory -> ECR draft & confirm

Supports W3C traceparent header injection to trace load-test requests in OpenTelemetry / Tempo.
"""

import json
import random
import uuid
from locust import HttpUser, task, between, tag

PART_NUMBERS = [
    "PMP-0001",
    "PMP-0002",
    "PMP-0010",
    "PMP-0020",
    "PMP-0050",
    "PMP-0100",
    "PMP-0102",
    "PMP-0290",
]

SEARCH_QUERIES = [
    "pump",
    "impeller",
    "bearing",
    "shaft",
    "casing",
    "seal",
    "valve",
    "motor",
]

LIFECYCLE_STATES = ["IN_WORK", "UNDER_REVIEW", "RELEASED", "OBSOLETE"]


def generate_w3c_headers() -> dict[str, str]:
    """Generate W3C traceparent and X-Request-ID headers for distributed trace linking."""
    trace_id = uuid.uuid4().hex
    span_id = uuid.uuid4().hex[:16]
    return {
        "traceparent": f"00-{trace_id}-{span_id}-01",
        "X-Request-ID": f"load-{uuid.uuid4().hex[:8]}",
        "Content-Type": "application/json",
    }


class PLMUser(HttpUser):
    """Unified user simulating typical engineering and governance workflows."""

    wait_time = between(0.5, 2.0)

    # -------------------------------------------------------------------------
    # 1. Part Catalog Tasks (Weight: 35)
    # -------------------------------------------------------------------------
    @tag("parts", "read")
    @task(20)
    def search_parts_by_query(self):
        query = random.choice(SEARCH_QUERIES)
        headers = generate_w3c_headers()
        self.client.get(
            f"/parts?query={query}&page=1&page_size=20",
            headers=headers,
            name="/parts?query=[term]",
        )

    @tag("parts", "read")
    @task(10)
    def filter_parts_by_state(self):
        state = random.choice(LIFECYCLE_STATES)
        headers = generate_w3c_headers()
        self.client.get(
            f"/parts?lifecycle_state={state}&page=1&page_size=20",
            headers=headers,
            name="/parts?lifecycle_state=[state]",
        )

    @tag("parts", "read")
    @task(15)
    def get_part_detail(self):
        part = random.choice(PART_NUMBERS)
        headers = generate_w3c_headers()
        self.client.get(
            f"/parts/{part}",
            headers=headers,
            name="/parts/[part_number]",
        )

    # -------------------------------------------------------------------------
    # 2. Bill of Materials (BOM) & Where-Used (Weight: 25)
    # -------------------------------------------------------------------------
    @tag("bom", "read")
    @task(12)
    def get_bom_hierarchy(self):
        part = random.choice(["PMP-0001", "PMP-0002", "PMP-0010"])
        headers = generate_w3c_headers()
        self.client.get(
            f"/parts/{part}/bom?levels=2",
            headers=headers,
            name="/parts/[part_number]/bom?levels=2",
        )

    @tag("bom", "read")
    @task(8)
    def get_where_used(self):
        part = random.choice(["PMP-0290", "PMP-0050", "PMP-0100"])
        headers = generate_w3c_headers()
        self.client.get(
            f"/parts/{part}/where-used?recursive=true",
            headers=headers,
            name="/parts/[part_number]/where-used",
        )

    @tag("bom", "write")
    @task(5)
    def compare_boms(self):
        headers = generate_w3c_headers()
        payload = {
            "assembly_a": "PMP-0001",
            "assembly_b": "PMP-0002",
        }
        self.client.post(
            "/bom/compare",
            headers=headers,
            json=payload,
            name="/bom/compare",
        )

    # -------------------------------------------------------------------------
    # 3. Change Impact Analysis (Weight: 15)
    # -------------------------------------------------------------------------
    @tag("impact", "read")
    @task(12)
    def run_impact_analysis(self):
        part = random.choice(["PMP-0010", "PMP-0290", "PMP-0050"])
        headers = generate_w3c_headers()
        payload = {"part_number": part}
        self.client.post(
            "/impact",
            headers=headers,
            json=payload,
            name="/impact",
        )

    # -------------------------------------------------------------------------
    # 4. AI Assistant Chat Interactions (Weight: 15)
    # -------------------------------------------------------------------------
    @tag("chat", "ai")
    @task(8)
    def chat_query_impact(self):
        headers = generate_w3c_headers()
        payload = {
            "message": "What is the blast radius impact of part PMP-0010?",
            "history": [],
        }
        # Consume streaming SSE response
        with self.client.post(
            "/chat",
            headers=headers,
            json=payload,
            name="/chat [impact]",
            catch_response=True,
            stream=True,
        ) as response:
            if response.status_code == 200:
                # Read chunks to complete the stream
                for _ in response.iter_lines():
                    pass
                response.success()
            else:
                response.failure(f"Chat failed with status {response.status_code}")

    @tag("chat", "ai")
    @task(7)
    def chat_query_obsolete_issues(self):
        headers = generate_w3c_headers()
        payload = {
            "message": "Find obsolete parts in released BOMs",
            "history": [],
        }
        with self.client.post(
            "/chat",
            headers=headers,
            json=payload,
            name="/chat [obsolete]",
            catch_response=True,
            stream=True,
        ) as response:
            if response.status_code == 200:
                for _ in response.iter_lines():
                    pass
                response.success()
            else:
                response.failure(f"Chat failed with status {response.status_code}")

    # -------------------------------------------------------------------------
    # 5. Closed-Loop Scenario: IIoT -> QMS -> PLM -> ERP -> ECR (Weight: 10)
    # -------------------------------------------------------------------------
    @tag("closed_loop", "lifecycle")
    @task(10)
    def execute_closed_loop_scenario(self):
        headers = generate_w3c_headers()

        # Step 1: Query Digital Thread (IIoT sensor anomalies + QMS defects + ERP stock)
        with self.client.get(
            "/digital-thread/PMP-0290",
            headers=headers,
            name="/digital-thread/PMP-0290 [closed_loop]",
            catch_response=True,
        ) as dt_res:
            if dt_res.status_code != 200:
                dt_res.failure(f"Failed digital-thread: {dt_res.status_code}")
                return
            dt_data = dt_res.json()

        # Step 2: Draft Change Request (ECR) addressing the defect
        draft_payload = {
            "title": f"LoadTest ECR: Upgrade PMP-0290 Bearing to Ceramic Hybrid ({uuid.uuid4().hex[:6]})",
            "reason": "Remediating IIoT vibration spike and QMS roller skewing defect DEF-2025-0042.",
            "category": "DESIGN_IMPROVEMENT",
            "priority": "HIGH",
            "affected_parts": ["PMP-0290"],
        }
        with self.client.post(
            "/changes/draft",
            headers=headers,
            json=draft_payload,
            name="/changes/draft [closed_loop]",
            catch_response=True,
        ) as draft_res:
            if draft_res.status_code != 200:
                draft_res.failure(f"Failed draft ECR: {draft_res.status_code}")
                return
            draft_id = draft_res.json().get("draft_id")

        # Step 3: Explicit Confirmation of the ECR (Two-Step Safety Gate)
        if draft_id:
            with self.client.post(
                f"/changes/{draft_id}/confirm",
                headers=headers,
                name="/changes/[id]/confirm [closed_loop]",
                catch_response=True,
            ) as confirm_res:
                if confirm_res.status_code not in (200, 201):
                    confirm_res.failure(f"Failed confirm ECR: {confirm_res.status_code}")
                else:
                    confirm_res.success()
