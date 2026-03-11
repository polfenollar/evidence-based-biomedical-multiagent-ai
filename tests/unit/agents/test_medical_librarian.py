"""Unit tests for the Medical Librarian agent node."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.agent_worker.agents.medical_librarian import make_medical_librarian

_BASE_URL = "http://retrieval-api:8001"


def _make_response(results: list[dict], status: int = 200) -> MagicMock:
    mock_resp = MagicMock()
    mock_resp.status_code = status
    mock_resp.json.return_value = {"results": results, "query": "test", "total": len(results)}
    mock_resp.raise_for_status = MagicMock()
    return mock_resp


def _doc(doc_id: str = "PMID:1", score: float = 0.9) -> dict:
    return {
        "doc_id": doc_id,
        "score": score,
        "title": f"Title {doc_id}",
        "snippet": f"Snippet for {doc_id}.",
        "source_type": "article",
        "iceberg_snapshot_ref": "snap-1",
        "indexing_run_id": "run-1",
    }


class TestMedicalLibrarian:
    def test_returns_docs_on_success(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.return_value = _make_response([_doc("PMID:1"), _doc("PMID:2")])
            result = librarian({"search_query": "aspirin", "search_limit": 5})
        assert len(result["retrieved_docs"]) == 2
        assert result["retrieved_docs"][0]["doc_id"] == "PMID:1"

    def test_sends_query_in_request_body(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.return_value = _make_response([])
            librarian({"search_query": "metformin diabetes", "search_limit": 10})
        _, kwargs = mock_post.call_args
        body = kwargs["json"]
        assert body["query"] == "metformin diabetes"
        assert body["limit"] == 10

    def test_includes_filters_in_request(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.return_value = _make_response([])
            librarian({
                "search_query": "aspirin",
                "search_limit": 5,
                "filters": {"source_type": "article"},
            })
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["filters"]["source_type"] == "article"

    def test_omits_filters_when_none(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.return_value = _make_response([])
            librarian({"search_query": "aspirin", "search_limit": 5, "filters": None})
        _, kwargs = mock_post.call_args
        assert "filters" not in kwargs["json"]

    def test_returns_empty_list_on_http_error(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.side_effect = Exception("connection refused")
            result = librarian({"search_query": "aspirin", "search_limit": 5})
        assert result["retrieved_docs"] == []

    def test_calls_correct_url(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.return_value = _make_response([])
            librarian({"search_query": "test", "search_limit": 3})
        args, _ = mock_post.call_args
        assert args[0] == f"{_BASE_URL}/v1/search"

    def test_falls_back_to_question_when_no_search_query(self) -> None:
        librarian = make_medical_librarian(_BASE_URL)
        with patch("src.agent_worker.agents.medical_librarian.httpx.post") as mock_post:
            mock_post.return_value = _make_response([])
            librarian({"question": "aspirin heart attack", "search_limit": 5})
        _, kwargs = mock_post.call_args
        assert kwargs["json"]["query"] == "aspirin heart attack"
