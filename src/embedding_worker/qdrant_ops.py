"""Qdrant collection and upsert/search helpers for the embedding worker."""
from __future__ import annotations

from typing import Any

import qdrant_client
from qdrant_client.models import Distance, FieldCondition, Filter, MatchValue, PointStruct, VectorParams


class QdrantOps:
    """Thin wrapper around :class:`qdrant_client.QdrantClient`.

    Parameters
    ----------
    url:
        Full URL to the Qdrant HTTP endpoint, e.g. ``http://qdrant:6333``.
    """

    def __init__(self, url: str) -> None:
        self._client = qdrant_client.QdrantClient(url=url)

    # ── Collection management ──────────────────────────────────────────────────

    def ensure_collection(self, name: str, dimension: int) -> None:
        """Create *name* if it does not already exist.

        Parameters
        ----------
        name:
            Collection name.
        dimension:
            Vector dimension (e.g. 384 for all-MiniLM-L6-v2).
        """
        existing = {c.name for c in self._client.get_collections().collections}
        if name not in existing:
            self._client.create_collection(
                collection_name=name,
                vectors_config=VectorParams(size=dimension, distance=Distance.COSINE),
            )

    # ── Write ──────────────────────────────────────────────────────────────────

    def upsert_batch(self, collection: str, points: list[PointStruct]) -> None:
        """Upsert a list of points into *collection*.

        Parameters
        ----------
        collection:
            Target collection name.
        points:
            Points to upsert.
        """
        self._client.upsert(collection_name=collection, points=points)

    # ── Read ───────────────────────────────────────────────────────────────────

    def search(
        self,
        collection: str,
        query_vector: list[float],
        limit: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Search *collection* by vector similarity.

        Parameters
        ----------
        collection:
            Collection to search.
        query_vector:
            Query embedding.
        limit:
            Maximum number of results.
        filters:
            Optional dict with keys ``source_type``, ``date_from``, ``date_to``.
            Translated to Qdrant :class:`Filter` conditions.

        Returns
        -------
        list[dict]
            Each dict contains: ``doc_id``, ``score``, ``title``, ``snippet``,
            ``source_type``, ``iceberg_snapshot_ref``, ``indexing_run_id``.
        """
        qdrant_filter: Filter | None = None

        if filters:
            must_conditions = []

            source_type = filters.get("source_type")
            if source_type:
                must_conditions.append(
                    FieldCondition(key="source_type", match=MatchValue(value=source_type))
                )

            if must_conditions:
                qdrant_filter = Filter(must=must_conditions)

        hits = self._client.query_points(
            collection_name=collection,
            query=query_vector,
            limit=limit,
            query_filter=qdrant_filter,
            with_payload=True,
        ).points

        results: list[dict[str, Any]] = []
        for hit in hits:
            payload = hit.payload or {}
            results.append(
                {
                    "doc_id": payload.get("doc_id", ""),
                    "score": hit.score,
                    "title": payload.get("title", ""),
                    "snippet": payload.get("snippet", ""),
                    "content": payload.get("content", ""),
                    "source_type": payload.get("source_type", ""),
                    "iceberg_snapshot_ref": payload.get("iceberg_snapshot_ref", ""),
                    "indexing_run_id": payload.get("indexing_run_id", ""),
                }
            )

        return results
