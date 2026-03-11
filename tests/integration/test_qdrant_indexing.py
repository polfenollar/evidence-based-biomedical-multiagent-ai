"""Integration tests for the Qdrant indexing pipeline.

These tests require a running Qdrant instance on localhost:6333.
Run with: pytest -m integration tests/integration/test_qdrant_indexing.py
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest

from src.embedding_worker.config import EmbeddingConfig
from src.embedding_worker.embedder import Embedder
from src.embedding_worker.jobs import index_articles, index_trials
from src.embedding_worker.qdrant_ops import QdrantOps

pytestmark = pytest.mark.integration

import os as _os
_QDRANT_URL = _os.environ.get("QDRANT_URL", "http://localhost:6333")

# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def qdrant() -> QdrantOps:
    return QdrantOps(url=_QDRANT_URL)


@pytest.fixture()
def embedder() -> Embedder:
    return Embedder(model_name="all-MiniLM-L6-v2", model_version="1")


@pytest.fixture()
def config() -> EmbeddingConfig:
    return EmbeddingConfig(
        qdrant_url=_QDRANT_URL,
        nessie_uri="http://nessie:19120/api/v2",
        temporal_address="temporal:7233",
        temporal_namespace="default",
        embedding_model="all-MiniLM-L6-v2",
        embedding_model_version="1",
        batch_size=32,
        pipeline_version="0.1.0",
    )


def _test_collection_name(prefix: str = "test") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _sample_articles(n: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "pmid": str(10000000 + i),
            "title": f"Effect of aspirin on cardiovascular outcomes: study {i}",
            "abstract": (
                f"This randomised controlled trial evaluated aspirin therapy in {i * 100} "
                "patients with coronary artery disease.  Primary endpoint was MACE at 12 months."
            ),
        }
        for i in range(n)
    ]


def _sample_trials(n: int = 3) -> list[dict[str, Any]]:
    return [
        {
            "nct_id": f"NCT0000{i:04d}",
            "brief_title": f"Metformin in type 2 diabetes mellitus: trial {i}",
            "conditions": "Type 2 Diabetes Mellitus",
            "interventions": "Metformin 500 mg twice daily",
        }
        for i in range(n)
    ]


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_create_collection(qdrant: QdrantOps) -> None:
    """ensure_collection should create a new collection that then exists."""
    col_name = _test_collection_name("create_col")
    try:
        qdrant.ensure_collection(col_name, dimension=384)
        existing = {c.name for c in qdrant._client.get_collections().collections}
        assert col_name in existing
    finally:
        try:
            qdrant._client.delete_collection(col_name)
        except Exception:  # noqa: BLE001
            pass


def test_index_and_search_articles(
    qdrant: QdrantOps,
    embedder: Embedder,
    config: EmbeddingConfig,
) -> None:
    """index_articles followed by a search should return relevant results."""
    col_name = _test_collection_name("articles")
    # Override collection name via a monkey-patched config/jobs call
    from src.embedding_worker import jobs as _jobs

    original = _jobs.ARTICLES_COLLECTION
    _jobs.ARTICLES_COLLECTION = col_name
    try:
        records = _sample_articles(3)
        run_id = str(uuid.uuid4())
        count = index_articles(
            records=records,
            snapshot_ref="snap-test-001",
            indexing_run_id=run_id,
            embedder=embedder,
            qdrant=qdrant,
            config=config,
        )
        assert count == 3

        results = qdrant.search(
            collection=col_name,
            query_vector=embedder.embed_single("cardiovascular aspirin"),
            limit=5,
        )
        assert len(results) > 0
        assert all("doc_id" in r for r in results)
        assert all(r["source_type"] == "article" for r in results)
    finally:
        _jobs.ARTICLES_COLLECTION = original
        try:
            qdrant._client.delete_collection(col_name)
        except Exception:  # noqa: BLE001
            pass


def test_search_with_source_type_filter(
    qdrant: QdrantOps,
    embedder: Embedder,
    config: EmbeddingConfig,
) -> None:
    """Filtering by source_type should return only matching documents."""
    from src.embedding_worker import jobs as _jobs

    articles_col = _test_collection_name("filter_articles")
    trials_col = _test_collection_name("filter_trials")

    original_articles = _jobs.ARTICLES_COLLECTION
    original_trials = _jobs.TRIALS_COLLECTION
    _jobs.ARTICLES_COLLECTION = articles_col
    _jobs.TRIALS_COLLECTION = trials_col

    try:
        run_id = str(uuid.uuid4())
        index_articles(
            records=_sample_articles(2),
            snapshot_ref="snap-test",
            indexing_run_id=run_id,
            embedder=embedder,
            qdrant=qdrant,
            config=config,
        )
        index_trials(
            records=_sample_trials(2),
            snapshot_ref="snap-test",
            indexing_run_id=run_id,
            embedder=embedder,
            qdrant=qdrant,
            config=config,
        )

        query_vector = embedder.embed_single("diabetes treatment")

        article_results = qdrant.search(
            collection=articles_col,
            query_vector=query_vector,
            limit=10,
            filters={"source_type": "article"},
        )
        trial_results = qdrant.search(
            collection=trials_col,
            query_vector=query_vector,
            limit=10,
            filters={"source_type": "trial"},
        )

        assert all(r["source_type"] == "article" for r in article_results)
        assert all(r["source_type"] == "trial" for r in trial_results)
    finally:
        _jobs.ARTICLES_COLLECTION = original_articles
        _jobs.TRIALS_COLLECTION = original_trials
        for col in (articles_col, trials_col):
            try:
                qdrant._client.delete_collection(col)
            except Exception:  # noqa: BLE001
                pass


def test_indexing_run_id_in_payload(
    qdrant: QdrantOps,
    embedder: Embedder,
    config: EmbeddingConfig,
) -> None:
    """Every indexed document must have indexing_run_id in its Qdrant payload."""
    from src.embedding_worker import jobs as _jobs

    col_name = _test_collection_name("runid_check")
    original = _jobs.ARTICLES_COLLECTION
    _jobs.ARTICLES_COLLECTION = col_name

    try:
        run_id = str(uuid.uuid4())
        index_articles(
            records=_sample_articles(3),
            snapshot_ref="snap-runid",
            indexing_run_id=run_id,
            embedder=embedder,
            qdrant=qdrant,
            config=config,
        )

        query_vector = embedder.embed_single("aspirin")
        results = qdrant.search(
            collection=col_name,
            query_vector=query_vector,
            limit=10,
        )

        assert len(results) == 3
        for r in results:
            assert r["indexing_run_id"] != ""
            assert r["iceberg_snapshot_ref"] == "snap-runid"
    finally:
        _jobs.ARTICLES_COLLECTION = original
        try:
            qdrant._client.delete_collection(col_name)
        except Exception:  # noqa: BLE001
            pass
