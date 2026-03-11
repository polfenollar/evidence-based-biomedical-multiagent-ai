"""Unit tests for the LangGraph multi-agent graph.

All external HTTP calls (retrieval-api, feature-api) are mocked so the
graph runs end-to-end without a live stack.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent_worker.agents.graph import build_graph


def _search_response(n: int = 2) -> dict:
    return {
        "results": [
            {
                "doc_id": f"PMID:{i}",
                "score": 0.9 - i * 0.05,
                "title": f"Title {i}",
                "snippet": f"Snippet for doc {i}. Important clinical finding.",
                "source_type": "article",
                "iceberg_snapshot_ref": "snap-abc",
                "indexing_run_id": "run-1",
            }
            for i in range(1, n + 1)
        ],
        "query": "aspirin",
        "total": n,
    }


def _feature_response(pmid: str) -> dict:
    return {
        "pmid": pmid,
        "abstract_word_count": 150,
        "publication_year": 2022,
        "has_abstract": True,
        "title_word_count": 10,
        "journal_encoded": 1,
        "snapshot_ref": "snap-abc",
        "feature_view_version": "article_stats",
    }


def _mock_post_for_search(results_n: int = 2) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = _search_response(results_n)
    return resp


def _mock_get_for_features(pmid: str = "1") -> MagicMock:
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _feature_response(pmid)
    return resp


class TestBuildGraph:
    def test_graph_compiles_without_error(self) -> None:
        graph = build_graph("http://retrieval:8001", "http://features:8002")
        assert graph is not None

    def test_graph_produces_approved_result(self) -> None:
        graph = build_graph("http://retrieval:8001", "http://features:8002")
        with (
            patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post,
            patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get,
        ):
            mock_post.return_value = _mock_post_for_search(2)
            mock_get.return_value = _mock_get_for_features()

            final = graph.invoke({
                "question": "Does aspirin reduce MI risk?",
                "filters": None,
                "query_id": "test-q-1",
                "search_query": "",
                "search_limit": 5,
                "retrieved_docs": [],
                "features": {},
                "answer": {},
                "citations": [],
                "revision_count": 0,
                "review_status": "pending",
                "review_feedback": "",
                "evidence_manifest_id": "",
            })

        assert final["review_status"] == "approved"
        assert len(final["citations"]) >= 1
        assert final["evidence_manifest_id"] != ""

    def test_graph_assigns_manifest_id(self) -> None:
        graph = build_graph("http://retrieval:8001", "http://features:8002")
        with (
            patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post,
            patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get,
        ):
            mock_post.return_value = _mock_post_for_search(1)
            mock_get.return_value = _mock_get_for_features()
            final = graph.invoke({
                "question": "aspirin",
                "filters": None,
                "query_id": "q-2",
                "search_query": "",
                "search_limit": 5,
                "retrieved_docs": [],
                "features": {},
                "answer": {},
                "citations": [],
                "revision_count": 0,
                "review_status": "pending",
                "review_feedback": "",
                "evidence_manifest_id": "",
            })
        assert final["evidence_manifest_id"]

    def test_graph_handles_no_retrieval_results(self) -> None:
        """Graph should complete gracefully even when librarian returns no docs."""
        graph = build_graph("http://retrieval:8001", "http://features:8002")
        with (
            patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post,
            patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get,
        ):
            mock_post.return_value = MagicMock(
                raise_for_status=MagicMock(),
                json=MagicMock(return_value={"results": [], "query": "x", "total": 0}),
            )
            mock_get.return_value = MagicMock(status_code=404)

            final = graph.invoke({
                "question": "unknown rare disease",
                "filters": None,
                "query_id": "q-3",
                "search_query": "",
                "search_limit": 5,
                "retrieved_docs": [],
                "features": {},
                "answer": {},
                "citations": [],
                "revision_count": 0,
                "review_status": "pending",
                "review_feedback": "",
                "evidence_manifest_id": "",
            })

        # With no docs, reviewer rejects but graph should still complete
        assert "evidence_manifest_id" in final
        assert final["evidence_manifest_id"] != ""

    def test_graph_retries_on_rejection_and_caps_revisions(self) -> None:
        """Reviewer rejects twice; graph should not loop infinitely."""
        graph = build_graph("http://retrieval:8001", "http://features:8002")
        # Return docs with empty snippets to force rejection
        empty_snippet_response = {
            "results": [
                {
                    "doc_id": "PMID:1",
                    "score": 0.8,
                    "title": "Title",
                    "snippet": "",          # empty → reviewer rejects
                    "source_type": "article",
                    "iceberg_snapshot_ref": "snap-1",
                    "indexing_run_id": "run-1",
                }
            ],
            "query": "test",
            "total": 1,
        }
        with (
            patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post,
            patch("src.agent_worker.agents.clinical_biostatistician.httpx.get") as mock_get,
        ):
            mock_post.return_value = MagicMock(
                raise_for_status=MagicMock(),
                json=MagicMock(return_value=empty_snippet_response),
            )
            mock_get.return_value = MagicMock(status_code=404)

            final = graph.invoke({
                "question": "aspirin",
                "filters": None,
                "query_id": "q-retry",
                "search_query": "",
                "search_limit": 5,
                "retrieved_docs": [],
                "features": {},
                "answer": {},
                "citations": [],
                "revision_count": 0,
                "review_status": "pending",
                "review_feedback": "",
                "evidence_manifest_id": "",
            })

        # After max revisions, finalize is always called
        assert final["revision_count"] >= 1
        assert "evidence_manifest_id" in final
