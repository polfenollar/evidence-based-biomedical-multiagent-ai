"""Core indexing jobs for the embedding worker.

These functions receive pre-fetched records (list of dicts) from the Temporal
activity layer and handle embedding + Qdrant upsert.  They do NOT read from
Iceberg directly; that is the responsibility of :mod:`spark_reader` and the
Temporal activities.
"""
from __future__ import annotations

import uuid
from typing import Any

from qdrant_client.models import PointStruct

from src.embedding_worker.config import EmbeddingConfig
from src.embedding_worker.embedder import Embedder
from src.embedding_worker.qdrant_ops import QdrantOps

# Collection names
ARTICLES_COLLECTION = "biomedical_articles"
TRIALS_COLLECTION = "biomedical_trials"

# Maximum characters kept as the "snippet" in the payload
_SNIPPET_MAX_CHARS = 500

# Maximum tokens for the text fed to the embedding model (approximate via chars)
_MAX_TEXT_CHARS = 2048  # ~512 tokens at ~4 chars/token


def _truncate(text: str, max_chars: int) -> str:
    """Return *text* truncated to *max_chars* characters."""
    return text[:max_chars] if len(text) > max_chars else text


def index_articles(
    records: list[dict[str, Any]],
    snapshot_ref: str,
    indexing_run_id: str,
    embedder: Embedder,
    qdrant: QdrantOps,
    config: EmbeddingConfig,
) -> int:
    """Embed curated articles and upsert them to the Qdrant articles collection.

    Parameters
    ----------
    records:
        List of dicts from ``nessie.biomedical.curated_articles``.
    snapshot_ref:
        Nessie/Iceberg snapshot identifier string.
    indexing_run_id:
        Unique identifier for this indexing run (stored in payload).
    embedder:
        Embedder instance to generate vectors.
    qdrant:
        QdrantOps instance for writing to Qdrant.
    config:
        EmbeddingConfig (used for batch_size and model metadata).

    Returns
    -------
    int
        Number of documents successfully indexed.
    """
    qdrant.ensure_collection(ARTICLES_COLLECTION, embedder.dimension)

    total_indexed = 0
    batch_size = config.batch_size

    for batch_start in range(0, len(records), batch_size):
        batch = records[batch_start : batch_start + batch_size]

        texts: list[str] = []
        for rec in batch:
            title = rec.get("title") or ""
            abstract = rec.get("abstract") or ""
            combined = f"{title} {abstract}".strip()
            texts.append(_truncate(combined, _MAX_TEXT_CHARS))

        vectors = embedder.embed_batch(texts)

        points: list[PointStruct] = []
        for rec, vector in zip(batch, vectors):
            pmid = rec.get("pmid") or str(uuid.uuid4())
            title = rec.get("title") or ""
            abstract = rec.get("abstract") or ""
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"PMID:{pmid}")),
                    vector=vector,
                    payload={
                        "doc_id": f"PMID:{pmid}",
                        "title": title,
                        "snippet": _truncate(abstract, _SNIPPET_MAX_CHARS),
                        "content": abstract,
                        "source_type": "article",
                        "embedding_model": config.embedding_model,
                        "embedding_model_version": config.embedding_model_version,
                        "indexing_run_id": indexing_run_id,
                        "iceberg_snapshot_ref": snapshot_ref,
                    },
                )
            )

        qdrant.upsert_batch(ARTICLES_COLLECTION, points)
        total_indexed += len(points)

    return total_indexed


def index_trials(
    records: list[dict[str, Any]],
    snapshot_ref: str,
    indexing_run_id: str,
    embedder: Embedder,
    qdrant: QdrantOps,
    config: EmbeddingConfig,
) -> int:
    """Embed curated clinical trials and upsert them to the Qdrant trials collection.

    Parameters
    ----------
    records:
        List of dicts from ``nessie.biomedical.curated_trials``.
    snapshot_ref:
        Nessie/Iceberg snapshot identifier string.
    indexing_run_id:
        Unique identifier for this indexing run (stored in payload).
    embedder:
        Embedder instance to generate vectors.
    qdrant:
        QdrantOps instance for writing to Qdrant.
    config:
        EmbeddingConfig (used for batch_size and model metadata).

    Returns
    -------
    int
        Number of documents successfully indexed.
    """
    qdrant.ensure_collection(TRIALS_COLLECTION, embedder.dimension)

    total_indexed = 0
    batch_size = config.batch_size

    for batch_start in range(0, len(records), batch_size):
        batch = records[batch_start : batch_start + batch_size]

        texts: list[str] = []
        for rec in batch:
            brief_title = rec.get("brief_title") or ""
            conditions = rec.get("conditions") or ""
            interventions = rec.get("interventions") or ""
            combined = " ".join(
                part for part in [brief_title, conditions, interventions] if part
            )
            texts.append(_truncate(combined, _MAX_TEXT_CHARS))

        vectors = embedder.embed_batch(texts)

        points: list[PointStruct] = []
        for rec, vector in zip(batch, vectors):
            nct_id = rec.get("nct_id") or str(uuid.uuid4())
            brief_title = rec.get("brief_title") or ""
            conditions = rec.get("conditions") or ""
            interventions = rec.get("interventions") or ""
            description = " ".join(
                part for part in [conditions, interventions] if part
            )
            points.append(
                PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_DNS, f"NCT:{nct_id}")),
                    vector=vector,
                    payload={
                        "doc_id": f"NCT:{nct_id}",
                        "title": brief_title,
                        "snippet": _truncate(description, _SNIPPET_MAX_CHARS),
                        "content": description,
                        "source_type": "trial",
                        "embedding_model": config.embedding_model,
                        "embedding_model_version": config.embedding_model_version,
                        "indexing_run_id": indexing_run_id,
                        "iceberg_snapshot_ref": snapshot_ref,
                    },
                )
            )

        qdrant.upsert_batch(TRIALS_COLLECTION, points)
        total_indexed += len(points)

    return total_indexed
