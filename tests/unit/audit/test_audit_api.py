"""Unit tests for the audit-api endpoints.

The Redis client and the Temporal/agent pipeline are mocked so these tests
run without any running infrastructure.
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient


def _make_manifest(manifest_id: str = "test-manifest-1") -> dict:
    return {
        "manifest_id": manifest_id,
        "query_id": "q-1",
        "question": "What is aspirin?",
        "filters": None,
        "answer": {
            "background": "BG",
            "evidence": "EV",
            "statistics": "ST",
            "conclusion": "CO",
        },
        "citations": [{"id": "PMID:1", "type": "article", "snippet": "Snippet."}],
        "review_status": "approved",
        "review_feedback": "",
        "retrieved_doc_count": 1,
        "feature_enriched_count": 1,
        "execution_timeline": [
            {"step": "cmo_router", "elapsed_ms": 2, "started_at": "2024-01-01T00:00:00Z"},
            {"step": "medical_librarian", "elapsed_ms": 120, "started_at": "2024-01-01T00:00:00.002Z"},
        ],
        "created_at": "2024-01-01T00:00:00Z",
    }


@pytest.fixture()
def audit_client():
    """Return a TestClient with a mocked Redis connection."""
    from src.audit_api.main import app, _redis
    import src.audit_api.main as _mod

    mock_redis = AsyncMock()
    _mod._redis = mock_redis
    yield TestClient(app), mock_redis
    _mod._redis = None


class TestAuditApiHealth:
    def test_health_returns_ok(self, audit_client) -> None:
        client, _ = audit_client
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        assert resp.json()["service"] == "audit-api"


class TestGetAudit:
    def test_returns_manifest_when_found(self, audit_client) -> None:
        client, mock_redis = audit_client
        manifest = _make_manifest("m-1")
        mock_redis.get = AsyncMock(return_value=json.dumps(manifest))

        resp = client.get("/v1/audit/m-1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["manifest_id"] == "m-1"
        assert data["review_status"] == "approved"

    def test_returns_404_when_not_found(self, audit_client) -> None:
        client, mock_redis = audit_client
        mock_redis.get = AsyncMock(return_value=None)

        resp = client.get("/v1/audit/nonexistent-id")
        assert resp.status_code == 404

    def test_timeline_present_in_response(self, audit_client) -> None:
        client, mock_redis = audit_client
        manifest = _make_manifest("m-2")
        mock_redis.get = AsyncMock(return_value=json.dumps(manifest))

        resp = client.get("/v1/audit/m-2")
        data = resp.json()
        assert "execution_timeline" in data
        assert len(data["execution_timeline"]) == 2

    def test_timeline_defaults_to_empty_list_when_missing(self, audit_client) -> None:
        client, mock_redis = audit_client
        manifest = _make_manifest("m-3")
        del manifest["execution_timeline"]
        mock_redis.get = AsyncMock(return_value=json.dumps(manifest))

        resp = client.get("/v1/audit/m-3")
        data = resp.json()
        assert data["execution_timeline"] == []

    def test_citations_present_in_response(self, audit_client) -> None:
        client, mock_redis = audit_client
        manifest = _make_manifest("m-4")
        mock_redis.get = AsyncMock(return_value=json.dumps(manifest))

        resp = client.get("/v1/audit/m-4")
        data = resp.json()
        assert len(data["citations"]) == 1
        assert data["citations"][0]["id"] == "PMID:1"

    def test_redis_503_on_exception(self, audit_client) -> None:
        client, mock_redis = audit_client
        mock_redis.get = AsyncMock(side_effect=Exception("Redis down"))

        resp = client.get("/v1/audit/m-err")
        assert resp.status_code == 503


class TestAgentApiRbac:
    """RBAC tests for agent-api operator endpoint."""

    @pytest.fixture()
    def agent_client(self):
        from src.agent_api.main import app
        import src.agent_api.main as _mod

        _mod._temporal_client = MagicMock()
        _mod._redis = AsyncMock()
        yield TestClient(app)
        _mod._temporal_client = None
        _mod._redis = None

    def test_operator_endpoint_returns_403_for_researcher(self, agent_client) -> None:
        resp = agent_client.get(
            "/v1/operator/queries",
            headers={"X-Role": "researcher"},
        )
        assert resp.status_code == 403

    def test_operator_endpoint_returns_403_with_no_role_header(self, agent_client) -> None:
        resp = agent_client.get("/v1/operator/queries")
        assert resp.status_code == 403

    def test_operator_endpoint_returns_200_for_operator(self, agent_client) -> None:
        resp = agent_client.get(
            "/v1/operator/queries",
            headers={"X-Role": "operator"},
        )
        assert resp.status_code == 200
        assert "query_ids" in resp.json()
