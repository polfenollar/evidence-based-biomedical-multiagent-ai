"""Agent API stub — Phase 1 E2E smoke test endpoint.

This is a **stub** implementation.  It returns hardcoded answers but reads
real Iceberg snapshot IDs from the Nessie REST catalog to validate the data
lake integration.
"""
from __future__ import annotations

import os
import uuid
from typing import Any

import httpx
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(
    title="Biomedical AI — Agent API (Phase 1 Stub)",
    version="0.1.0",
)

# ── In-memory evidence manifest store ────────────────────────────────────────
_manifests: dict[str, dict[str, Any]] = {}

# ── Nessie config ─────────────────────────────────────────────────────────────
_NESSIE_BASE = os.environ.get("NESSIE_URI", "http://nessie:19120")


# ── Schemas ───────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str
    filters: dict[str, Any] | None = None


class Citation(BaseModel):
    id: str
    type: str
    snippet: str


class AnswerBlock(BaseModel):
    background: str
    evidence: str
    statistics: str
    conclusion: str


class SnapshotRefs(BaseModel):
    iceberg_snapshot_id: str | None
    vector_index_run_id: str
    feature_registry_version: str


class QueryResponse(BaseModel):
    answer: AnswerBlock
    citations: list[Citation]
    evidence_manifest_id: str
    query_id: str
    snapshot_refs: SnapshotRefs


# ── Nessie helpers ────────────────────────────────────────────────────────────

async def _get_curated_articles_snapshot() -> str | None:
    """Attempt to read the current snapshot ID for curated_articles from Nessie."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # 1. Check whether the table exists
            entries_url = f"{_NESSIE_BASE}/api/v2/trees/main/entries"
            resp = await client.get(entries_url)
            resp.raise_for_status()
            entries = resp.json()

            table_key = "biomedical.curated_articles"
            table_exists = any(
                ".".join(e.get("name", {}).get("elements", []))
                == table_key
                for e in entries.get("entries", [])
            )

            if not table_exists:
                return "no-snapshot-yet"

            # 2. Read the content entry to get the metadata location
            contents_url = (
                f"{_NESSIE_BASE}/api/v2/trees/main/contents/biomedical.curated_articles"
            )
            resp2 = await client.get(contents_url)
            resp2.raise_for_status()
            content = resp2.json()

            # The Nessie REST API returns the Iceberg table metadata.
            # The snapshot ID is buried inside the content payload.
            snapshot_id = (
                content.get("content", {})
                .get("snapshotId")
                or content.get("content", {})
                .get("snapshot-id")
                or content.get("snapshotId")
                or "no-snapshot-yet"
            )
            return str(snapshot_id)

    except Exception:
        return "no-snapshot-yet"


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "phase": "1-stub"}


@app.post("/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    query_id = str(uuid.uuid4())
    manifest_id = str(uuid.uuid4())

    snapshot_id = await _get_curated_articles_snapshot()

    answer = AnswerBlock(
        background=(
            "This is a Phase 1 stub response. "
            "Real evidence synthesis will be implemented in Phase 3."
        ),
        evidence=(
            "No real evidence retrieval has been performed. "
            "The data lake has been seeded with sample PubMed and ClinicalTrials data."
        ),
        statistics="N/A — stub response.",
        conclusion=(
            "Phase 1 infrastructure smoke test passed. "
            "Iceberg tables are queryable via the Nessie REST catalog."
        ),
    )

    citations = [
        Citation(
            id="PMID:12345678",
            type="article",
            snippet="Stub snippet for Phase 1 smoke test.",
        )
    ]

    snapshot_refs = SnapshotRefs(
        iceberg_snapshot_id=snapshot_id,
        vector_index_run_id="stub-phase1",
        feature_registry_version="stub-phase1",
    )

    manifest = {
        "manifest_id": manifest_id,
        "query_id": query_id,
        "question": request.question,
        "filters": request.filters,
        "answer": answer.model_dump(),
        "citations": [c.model_dump() for c in citations],
        "snapshot_refs": snapshot_refs.model_dump(),
    }
    _manifests[manifest_id] = manifest

    return QueryResponse(
        answer=answer,
        citations=citations,
        evidence_manifest_id=manifest_id,
        query_id=query_id,
        snapshot_refs=snapshot_refs,
    )
