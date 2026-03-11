"""Unit tests for the QdrantOps class.

The qdrant_client.QdrantClient is mocked so these tests run without a
running Qdrant instance.
"""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, call, patch

import pytest

from src.embedding_worker.qdrant_ops import QdrantOps


def _make_mock_client() -> MagicMock:
    """Return a MagicMock that mimics a QdrantClient instance."""
    mock = MagicMock()
    # Default: no existing collections
    mock.get_collections.return_value.collections = []
    return mock


def _make_search_hit(
    doc_id: str = "PMID:1",
    score: float = 0.9,
    source_type: str = "article",
    indexing_run_id: str = "run-1",
    snapshot_ref: str = "snap-abc",
) -> MagicMock:
    hit = MagicMock()
    hit.score = score
    hit.payload = {
        "doc_id": doc_id,
        "title": "Test Title",
        "snippet": "Test snippet.",
        "source_type": source_type,
        "iceberg_snapshot_ref": snapshot_ref,
        "indexing_run_id": indexing_run_id,
    }
    return hit


class TestQdrantOps(unittest.TestCase):
    """Tests for src.embedding_worker.qdrant_ops.QdrantOps."""

    # ── ensure_collection ──────────────────────────────────────────────────────

    def test_ensure_collection_creates_when_not_exists(self) -> None:
        """ensure_collection should call create_collection for a new name."""
        mock_client = _make_mock_client()
        mock_client.get_collections.return_value.collections = []

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            ops.ensure_collection("my_collection", dimension=384)

        mock_client.create_collection.assert_called_once()
        call_kwargs = mock_client.create_collection.call_args
        assert call_kwargs.kwargs["collection_name"] == "my_collection"

    def test_ensure_collection_skips_when_exists(self) -> None:
        """ensure_collection should NOT call create_collection if it already exists."""
        existing = MagicMock()
        existing.name = "existing_collection"
        mock_client = _make_mock_client()
        mock_client.get_collections.return_value.collections = [existing]

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            ops.ensure_collection("existing_collection", dimension=384)

        mock_client.create_collection.assert_not_called()

    def test_ensure_collection_uses_cosine_distance(self) -> None:
        """ensure_collection should create the collection with COSINE distance."""
        from qdrant_client.models import Distance

        mock_client = _make_mock_client()

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            ops.ensure_collection("new_col", dimension=128)

        _, kwargs = mock_client.create_collection.call_args
        vectors_config = kwargs["vectors_config"]
        assert vectors_config.distance == Distance.COSINE
        assert vectors_config.size == 128

    # ── upsert_batch ───────────────────────────────────────────────────────────

    def test_upsert_batch_calls_client_upsert(self) -> None:
        """upsert_batch should call client.upsert with the given points."""
        from qdrant_client.models import PointStruct

        mock_client = _make_mock_client()
        points = [
            PointStruct(id="1", vector=[0.1] * 384, payload={"doc_id": "PMID:1"}),
        ]

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            ops.upsert_batch("my_collection", points)

        mock_client.upsert.assert_called_once_with(
            collection_name="my_collection", points=points
        )

    # ── search ─────────────────────────────────────────────────────────────────

    def _setup_query_points_mock(self, mock_client: MagicMock, hits: list) -> None:
        """Set up query_points mock to return a result with .points attribute."""
        result = MagicMock()
        result.points = hits
        mock_client.query_points.return_value = result

    def test_search_returns_correctly_shaped_dicts(self) -> None:
        """search should return a list of dicts with the expected keys."""
        mock_client = _make_mock_client()
        self._setup_query_points_mock(mock_client, [_make_search_hit()])

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            results = ops.search("col", query_vector=[0.0] * 384, limit=5)

        assert len(results) == 1
        result = results[0]
        expected_keys = {"doc_id", "score", "title", "snippet", "source_type", "iceberg_snapshot_ref", "indexing_run_id"}
        assert set(result.keys()) == expected_keys
        assert result["doc_id"] == "PMID:1"
        assert result["score"] == 0.9

    def test_search_with_source_type_filter_passes_filter(self) -> None:
        """search with source_type filter should pass a Filter object to the client."""
        mock_client = _make_mock_client()
        self._setup_query_points_mock(mock_client, [])

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            ops.search(
                "col",
                query_vector=[0.0] * 384,
                limit=10,
                filters={"source_type": "article"},
            )

        _, kwargs = mock_client.query_points.call_args
        assert kwargs.get("query_filter") is not None

    def test_search_without_filter_passes_none_filter(self) -> None:
        """search with no filters should pass query_filter=None to the client."""
        mock_client = _make_mock_client()
        self._setup_query_points_mock(mock_client, [])

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            ops.search("col", query_vector=[0.0] * 384, limit=10, filters=None)

        _, kwargs = mock_client.query_points.call_args
        assert kwargs.get("query_filter") is None

    def test_search_multiple_hits(self) -> None:
        """search should return all hits returned by the client."""
        mock_client = _make_mock_client()
        self._setup_query_points_mock(mock_client, [
            _make_search_hit(doc_id="PMID:1", score=0.95),
            _make_search_hit(doc_id="PMID:2", score=0.80),
            _make_search_hit(doc_id="PMID:3", score=0.70),
        ])

        with patch("src.embedding_worker.qdrant_ops.qdrant_client.QdrantClient", return_value=mock_client):
            ops = QdrantOps(url="http://localhost:6333")
            results = ops.search("col", query_vector=[0.1] * 384, limit=3)

        assert len(results) == 3
        assert results[0]["doc_id"] == "PMID:1"
        assert results[1]["doc_id"] == "PMID:2"


if __name__ == "__main__":
    unittest.main()
