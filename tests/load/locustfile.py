"""Locust load test for the Biomedical AI Agent API.

Usage
-----
    # Install: pip install locust
    # Run against local stack:
    locust -f tests/load/locustfile.py --host=http://localhost:8003 \
        --users=10 --spawn-rate=2 --run-time=60s --headless

    # Or via Makefile:
    make load-test

P95 latency target (NFR-P2): ≤ 30 s under 10 concurrent users.
Success rate target (NFR-P4): ≥ 95% of requests return HTTP 200.
"""
from __future__ import annotations

import random

from locust import HttpUser, between, task

_GOLDEN_QUESTIONS = [
    "What is the effect of aspirin on cardiovascular outcomes?",
    "How effective is metformin for type 2 diabetes management?",
    "What are the side effects of beta-blockers in heart failure?",
    "Does statin therapy reduce mortality in coronary artery disease?",
    "What is the evidence for aspirin in primary prevention?",
]


class BiomedicaResearcher(HttpUser):
    """Simulates a researcher submitting queries to the agent pipeline."""

    wait_time = between(2, 5)   # 2–5 s think time between requests
    host = "http://localhost:8003"

    @task(3)
    def query_non_streaming(self) -> None:
        """POST /v1/query — durable Temporal workflow path."""
        question = random.choice(_GOLDEN_QUESTIONS)
        with self.client.post(
            "/v1/query",
            json={"question": question},
            headers={"X-Role": "researcher"},
            timeout=120,
            catch_response=True,
            name="POST /v1/query",
        ) as resp:
            if resp.status_code == 200:
                data = resp.json()
                if not data.get("citations"):
                    resp.failure("Response had no citations (DQ-UI-1 violation)")
                else:
                    resp.success()
            elif resp.status_code == 422:
                # DQ violation — count as failure
                resp.failure(f"DQ violation: {resp.text[:200]}")
            else:
                resp.failure(f"HTTP {resp.status_code}")

    @task(1)
    def health_check(self) -> None:
        """GET /health — lightweight liveness check."""
        self.client.get("/health", name="GET /health")

    @task(1)
    def operator_queries(self) -> None:
        """GET /v1/operator/queries — operator endpoint."""
        with self.client.get(
            "/v1/operator/queries",
            headers={"X-Role": "operator"},
            catch_response=True,
            name="GET /v1/operator/queries",
        ) as resp:
            if resp.status_code == 200:
                resp.success()
            else:
                resp.failure(f"HTTP {resp.status_code}")
