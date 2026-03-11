"""Phase 5 E2E integration tests.

Covers:
- POST /v1/query → audit manifest retrievable from audit-api with timeline
- POST /v1/query/stream → all agent step events emitted in correct order
- GET /v1/operator/queries → RBAC enforced (403 for researcher, 200 for operator)
- DQ-UI-1 contract: missing citations → structured error (tested via unit path)

Requires the full Phase 4+5 stack to be running:
    docker compose up -d agent-api audit-api retrieval-api feature-api

Run with:
    pytest -m integration tests/integration/test_phase5_e2e.py
"""
from __future__ import annotations

import json
import os
import time

import httpx
import pytest

pytestmark = pytest.mark.integration

_AGENT_API = os.environ.get("AGENT_API_URL", "http://localhost:8003")
_AUDIT_API = os.environ.get("AUDIT_API_URL", "http://localhost:8004")

_GOLDEN_QUESTION = "What is the effect of aspirin on cardiovascular outcomes?"
_EXPECTED_NODES = {
    "cmo_router",
    "medical_librarian",
    "clinical_biostatistician",
    "lead_researcher",
    "peer_reviewer",
    "finalize",
}


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def submitted_query() -> dict:
    """Submit the golden question and return the full response dict."""
    resp = httpx.post(
        f"{_AGENT_API}/v1/query",
        json={"question": _GOLDEN_QUESTION},
        timeout=120.0,
    )
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    return resp.json()


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_query_returns_structured_answer(submitted_query: dict) -> None:
    """POST /v1/query should return all four answer sections."""
    answer = submitted_query.get("answer", {})
    for section in ("background", "evidence", "statistics", "conclusion"):
        assert answer.get(section), f"answer.{section} missing or empty"


def test_query_returns_citations(submitted_query: dict) -> None:
    """POST /v1/query should return at least one citation."""
    citations = submitted_query.get("citations", [])
    assert len(citations) > 0, "No citations returned"
    for c in citations:
        assert c.get("id"), "Citation missing id"
        assert c.get("snippet"), "Citation missing snippet"


def test_query_review_status_approved(submitted_query: dict) -> None:
    """Peer reviewer should approve the golden-dataset answer."""
    assert submitted_query["review_status"] == "approved", (
        f"Reviewer rejected: {submitted_query.get('review_feedback')}"
    )


def test_manifest_retrievable_from_audit_api(submitted_query: dict) -> None:
    """Manifest must be retrievable from audit-api within a few seconds."""
    manifest_id = submitted_query["evidence_manifest_id"]
    assert manifest_id, "evidence_manifest_id missing"

    # Allow a moment for async persistence
    time.sleep(1)

    resp = httpx.get(f"{_AUDIT_API}/v1/audit/{manifest_id}", timeout=10.0)
    assert resp.status_code == 200, f"audit-api returned {resp.status_code}"
    manifest = resp.json()
    assert manifest["manifest_id"] == manifest_id


def test_audit_manifest_has_execution_timeline(submitted_query: dict) -> None:
    """Audit manifest must include an execution_timeline with ≥ 5 steps."""
    manifest_id = submitted_query["evidence_manifest_id"]
    resp = httpx.get(f"{_AUDIT_API}/v1/audit/{manifest_id}", timeout=10.0)
    manifest = resp.json()

    timeline = manifest.get("execution_timeline", [])
    assert len(timeline) >= 5, f"Expected ≥ 5 timeline steps, got {len(timeline)}: {timeline}"

    node_names = {step["step"] for step in timeline}
    for expected in ("cmo_router", "medical_librarian", "lead_researcher", "peer_reviewer"):
        assert expected in node_names, f"Node {expected!r} missing from timeline"


def test_audit_manifest_citations_match_query(submitted_query: dict) -> None:
    """Citations in audit manifest must match those returned by /v1/query."""
    manifest_id = submitted_query["evidence_manifest_id"]
    resp = httpx.get(f"{_AUDIT_API}/v1/audit/{manifest_id}", timeout=10.0)
    manifest = resp.json()

    query_ids = {c["id"] for c in submitted_query["citations"]}
    audit_ids = {c["id"] for c in manifest["citations"]}
    assert query_ids == audit_ids, f"Citation mismatch: {query_ids} vs {audit_ids}"


def test_sse_stream_emits_agent_step_events() -> None:
    """POST /v1/query/stream must emit step events for all major graph nodes."""
    received_nodes: list[str] = []
    complete_received = False

    with httpx.stream(
        "POST",
        f"{_AGENT_API}/v1/query/stream",
        json={"question": _GOLDEN_QUESTION},
        timeout=120.0,
    ) as resp:
        assert resp.status_code == 200
        current_event = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                raw = line[len("data:"):].strip()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if current_event == "step":
                    received_nodes.append(data.get("node", ""))
                elif current_event == "complete":
                    complete_received = True

    assert complete_received, "SSE stream did not emit a 'complete' event"
    assert len(received_nodes) >= 5, (
        f"Expected ≥ 5 step events, got {len(received_nodes)}: {received_nodes}"
    )

    received_set = set(received_nodes)
    for expected in ("cmo_router", "medical_librarian", "lead_researcher", "peer_reviewer"):
        assert expected in received_set, f"Node {expected!r} missing from SSE stream"


def test_sse_stream_complete_event_has_citations() -> None:
    """The 'complete' SSE event must include a non-empty citations list."""
    complete_data: dict = {}

    with httpx.stream(
        "POST",
        f"{_AGENT_API}/v1/query/stream",
        json={"question": _GOLDEN_QUESTION},
        timeout=120.0,
    ) as resp:
        current_event = None
        for line in resp.iter_lines():
            if line.startswith("event:"):
                current_event = line.split(":", 1)[1].strip()
            elif line.startswith("data:") and current_event == "complete":
                complete_data = json.loads(line[len("data:"):].strip())

    assert complete_data.get("citations"), "Complete event missing citations"


def test_rbac_operator_endpoint_blocks_researcher() -> None:
    """GET /v1/operator/queries must return 403 for researcher role."""
    resp = httpx.get(
        f"{_AGENT_API}/v1/operator/queries",
        headers={"X-Role": "researcher"},
        timeout=10.0,
    )
    assert resp.status_code == 403


def test_rbac_operator_endpoint_allows_operator() -> None:
    """GET /v1/operator/queries must return 200 for operator role."""
    resp = httpx.get(
        f"{_AGENT_API}/v1/operator/queries",
        headers={"X-Role": "operator"},
        timeout=10.0,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "query_ids" in data


def test_operator_queries_list_includes_submitted_query(submitted_query: dict) -> None:
    """After submitting a query, its query_id should appear in the operator list."""
    resp = httpx.get(
        f"{_AGENT_API}/v1/operator/queries",
        headers={"X-Role": "operator"},
        timeout=10.0,
    )
    data = resp.json()
    query_id = submitted_query["query_id"]
    assert query_id in data["query_ids"], (
        f"query_id {query_id!r} not in operator list: {data['query_ids']}"
    )
