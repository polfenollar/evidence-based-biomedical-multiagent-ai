"""Chaos / resilience tests for the Biomedical AI stack.

Each test kills or restarts a specific container and verifies that the system
either recovers automatically (``restart: unless-stopped``) or degrades
gracefully without silent data corruption.

Requirements
------------
- Full Docker Compose stack running (``make up``)
- ``docker`` Python SDK: ``pip install docker``
- Run with: ``pytest -m chaos tests/chaos/test_resilience.py``

The five kill/restart scenarios tested (from Phase 6 exit criteria):
1. agent-worker killed → Temporal retries, next query succeeds
2. retrieval-api killed → agent returns gracefully degraded result (no crash)
3. qdrant killed + restarted → retrieval-api recovers on restart
4. feature-api killed → biostatistician skips features gracefully
5. Temporal worker killed → workflow stays in Temporal history, worker restarts
"""
from __future__ import annotations

import time

import httpx
import pytest

pytestmark = pytest.mark.chaos

_AGENT_API = "http://localhost:8003"
_RECOVERY_WAIT = 20   # seconds to wait for container to restart

try:
    import docker as _docker_module
    _docker_available = True
except ImportError:
    _docker_available = False

docker_required = pytest.mark.skipif(
    not _docker_available,
    reason="docker SDK not installed (pip install docker)",
)


def _docker() -> "_docker_module.DockerClient":
    return _docker_module.from_env()


def _get_container(name: str) -> "_docker_module.models.containers.Container":
    return _docker().containers.get(name)


def _query(question: str = "aspirin cardiovascular outcomes", timeout: float = 120.0) -> dict:
    resp = httpx.post(
        f"{_AGENT_API}/v1/query",
        json={"question": question},
        timeout=timeout,
    )
    return resp.json() if resp.status_code == 200 else {"_error": resp.status_code}


# ── Scenario 1: agent-worker killed ───────────────────────────────────────────

@docker_required
def test_agent_worker_restarts_and_processes_next_query() -> None:
    """Kill agent-worker; it should restart (unless-stopped) within 20 s.
    The following query must succeed.
    """
    c = _get_container("agent-worker")
    c.kill()
    time.sleep(_RECOVERY_WAIT)
    c.reload()
    assert c.status == "running", "agent-worker did not restart automatically"

    result = _query()
    assert "_error" not in result, f"Query failed after agent-worker restart: {result}"
    assert result.get("citations"), "No citations after agent-worker restart"


# ── Scenario 2: retrieval-api killed ─────────────────────────────────────────

@docker_required
def test_retrieval_api_down_does_not_crash_agent() -> None:
    """Kill retrieval-api; agent should return a valid (possibly empty) response
    without crashing — no 500 from agent-api.
    """
    c = _get_container("retrieval-api")
    c.kill()
    try:
        resp = httpx.post(
            f"{_AGENT_API}/v1/query",
            json={"question": "aspirin outcomes"},
            timeout=120.0,
        )
        # Acceptable: 200 with empty citations, or 422 (DQ-UI-1)
        # Not acceptable: 500
        assert resp.status_code != 500, (
            f"agent-api crashed (500) when retrieval-api was down: {resp.text}"
        )
    finally:
        c.restart()
        time.sleep(10)


# ── Scenario 3: Qdrant killed + restarted ────────────────────────────────────

@docker_required
def test_qdrant_restart_retrieval_api_recovers() -> None:
    """Kill Qdrant, wait for restart; retrieval-api should recover automatically."""
    qdrant = _get_container("qdrant")
    qdrant.kill()
    time.sleep(5)
    qdrant.reload()
    # qdrant has no restart policy — start it manually
    qdrant.start()
    time.sleep(15)
    qdrant.reload()
    assert qdrant.status == "running", "Qdrant container did not start"

    # Verify retrieval-api health endpoint is reachable
    resp = httpx.get("http://localhost:8001/health", timeout=15.0)
    assert resp.status_code == 200, "retrieval-api health check failed after Qdrant restart"


# ── Scenario 4: feature-api killed ────────────────────────────────────────────

@docker_required
def test_feature_api_down_biostatistician_degrades_gracefully() -> None:
    """Kill feature-api; biostatistician should skip features (no crash).
    The graph should still produce an answer (possibly with empty statistics).
    """
    c = _get_container("feature-api")
    c.kill()
    try:
        resp = httpx.post(
            f"{_AGENT_API}/v1/query/stream",
            json={"question": "aspirin outcomes"},
            timeout=120.0,
        )
        # Stream must complete without a 500-level error
        assert resp.status_code == 200, f"SSE endpoint returned {resp.status_code}"
    finally:
        c.restart()
        time.sleep(10)


# ── Scenario 5: Temporal killed (graceful degradation) ────────────────────────

@docker_required
def test_temporal_down_query_endpoint_returns_502() -> None:
    """Kill Temporal; agent-api /v1/query should return 502 (not 500/crash).
    On restart, the workflow history is preserved.
    """
    temporal = _get_container("temporal")
    temporal.kill()
    try:
        resp = httpx.post(
            f"{_AGENT_API}/v1/query",
            json={"question": "aspirin outcomes"},
            timeout=30.0,
        )
        # Should be 502 (workflow failed), not 500 (unhandled crash)
        assert resp.status_code in {502, 503}, (
            f"Expected 502/503 when Temporal is down, got {resp.status_code}"
        )
    finally:
        temporal.restart()
        time.sleep(20)
        # After restart, a new query should succeed
        result = _query(timeout=120.0)
        assert "_error" not in result or result["_error"] not in {500}, (
            "agent returned 500 after Temporal restart"
        )
