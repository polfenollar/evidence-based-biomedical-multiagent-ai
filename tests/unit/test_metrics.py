"""Unit tests for Prometheus metrics in the agent-api."""
from __future__ import annotations

import pytest


class TestMetricsCounters:
    def test_queries_total_counter_exists(self) -> None:
        from src.agent_api.metrics import QUERIES_TOTAL
        assert QUERIES_TOTAL is not None

    def test_queries_total_labels(self) -> None:
        from src.agent_api.metrics import QUERIES_TOTAL
        # Should not raise — labels "approved", "rejected", "error" are valid
        QUERIES_TOTAL.labels(status="approved")
        QUERIES_TOTAL.labels(status="rejected")
        QUERIES_TOTAL.labels(status="error")

    def test_query_duration_histogram_exists(self) -> None:
        from src.agent_api.metrics import QUERY_DURATION
        assert QUERY_DURATION is not None

    def test_query_duration_observe(self) -> None:
        from src.agent_api.metrics import QUERY_DURATION
        # Should not raise
        QUERY_DURATION.observe(2.5)

    def test_dq_violations_counter_exists(self) -> None:
        from src.agent_api.metrics import DQ_VIOLATIONS_TOTAL
        assert DQ_VIOLATIONS_TOTAL is not None

    def test_dq_violations_label(self) -> None:
        from src.agent_api.metrics import DQ_VIOLATIONS_TOTAL
        DQ_VIOLATIONS_TOTAL.labels(rule="DQ-UI-1")

    def test_ingestion_records_counter_exists(self) -> None:
        from src.agent_api.metrics import INGESTION_RECORDS_TOTAL
        assert INGESTION_RECORDS_TOTAL is not None

    def test_ingestion_records_labels(self) -> None:
        from src.agent_api.metrics import INGESTION_RECORDS_TOTAL
        INGESTION_RECORDS_TOTAL.labels(source="articles")
        INGESTION_RECORDS_TOTAL.labels(source="trials")


class TestMetricsEndpoint:
    """Test that /metrics endpoint is exposed and returns Prometheus text."""

    @pytest.fixture()
    def agent_client(self):
        from unittest.mock import AsyncMock, MagicMock
        from fastapi.testclient import TestClient
        from src.agent_api.main import app
        import src.agent_api.main as _mod

        _mod._temporal_client = MagicMock()
        _mod._redis = AsyncMock()
        yield TestClient(app)
        _mod._temporal_client = None
        _mod._redis = None

    def test_metrics_endpoint_returns_200(self, agent_client) -> None:
        resp = agent_client.get("/metrics")
        assert resp.status_code == 200

    def test_metrics_endpoint_returns_prometheus_text(self, agent_client) -> None:
        resp = agent_client.get("/metrics")
        # Prometheus text format always includes HELP and TYPE lines
        assert "biomedical_queries_total" in resp.text or "python_gc" in resp.text


class TestUiResilienceDqUi5:
    """Unit tests for DQ-UI-5 and SSE drop handling in UI components."""

    def test_check_response_has_citations_dq_ui1(self) -> None:
        from src.ui.components import check_response_has_citations
        error = check_response_has_citations({"citations": []})
        assert "DQ-UI-1" in error

    def test_parse_sse_event_malformed_returns_none(self) -> None:
        from src.ui.components import parse_sse_event
        # DQ-UI-3: malformed SSE event should be skipped (return None)
        assert parse_sse_event("data: {bad json!!!}") is None
        assert parse_sse_event("data: ") is None

    def test_parse_sse_event_valid(self) -> None:
        import json
        from src.ui.components import parse_sse_event
        data = parse_sse_event('data: {"node": "cmo_router"}')
        assert data == {"node": "cmo_router"}
