"""Agent API — Phase 4/5/6 implementation.

Endpoints
---------
GET  /health                 — liveness probe
GET  /metrics                — Prometheus metrics
POST /v1/query               — submit question via Temporal EvidenceWorkflow
POST /v1/query/stream        — submit question with SSE per-step streaming
GET  /v1/manifest/{id}       — retrieve stored evidence manifest by ID
GET  /v1/operator/queries    — list recent query IDs (Operator role only)
"""
from __future__ import annotations

import asyncio
import datetime
import json
import logging
import queue as _queue
import threading
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, Header, HTTPException
from prometheus_client import make_asgi_app
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse
from temporalio.client import Client

from src.agent_api.config import get_config
from src.agent_api.metrics import DQ_VIOLATIONS_TOTAL, QUERIES_TOTAL, QUERY_DURATION

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_TASK_QUEUE = "agent"
_MANIFEST_TTL = 86_400  # 24 h


# ── App state ──────────────────────────────────────────────────────────────────

_temporal_client: Client | None = None
_redis: aioredis.Redis | None = None
_recent_query_ids: list[str] = []   # simple in-memory log for operator dashboard


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[type-arg]
    global _temporal_client, _redis  # noqa: PLW0603
    config = get_config()

    logger.info("Connecting to Temporal at %s …", config.temporal_address)
    _temporal_client = await Client.connect(
        config.temporal_address,
        namespace=config.temporal_namespace,
    )

    redis_url = (
        f"redis://:{config.redis_password}@{config.redis_host}:{config.redis_port}"
        if config.redis_password
        else f"redis://{config.redis_host}:{config.redis_port}"
    )
    logger.info("Connecting to Redis at %s:%d …", config.redis_host, config.redis_port)
    _redis = aioredis.from_url(redis_url, decode_responses=True)

    logger.info("Agent API ready.")
    yield

    if _redis:
        await _redis.aclose()
    _temporal_client = None
    _redis = None


app = FastAPI(
    title="Biomedical AI — Agent API",
    version="6.0.0",
    lifespan=_lifespan,
)

# Expose Prometheus metrics at /metrics
app.mount("/metrics", make_asgi_app())


# ── RBAC ───────────────────────────────────────────────────────────────────────


def _get_role(x_role: str = Header(default="researcher")) -> str:
    """Extract caller role from ``X-Role`` request header."""
    return x_role.lower()


def _require_operator(role: str = Depends(_get_role)) -> str:
    if role != "operator":
        raise HTTPException(status_code=403, detail="Operator role required")
    return role


# ── Request / Response models ──────────────────────────────────────────────────


class QueryRequest(BaseModel):
    question: str
    filters: dict[str, Any] | None = None


class Citation(BaseModel):
    id: str
    type: str
    snippet: str
    score: float = 0.0
    title: str = ""
    content: str = ""
    iceberg_snapshot_ref: str = ""


class AnswerBlock(BaseModel):
    background: str
    evidence: str
    statistics: str
    conclusion: str


class QueryResponse(BaseModel):
    answer: AnswerBlock
    citations: list[Citation]
    evidence_manifest_id: str
    query_id: str
    review_status: str
    review_feedback: str
    retrieved_doc_count: int
    feature_enriched_count: int


# ── Manifest helpers ───────────────────────────────────────────────────────────


async def _save_manifest(manifest: dict[str, Any]) -> None:
    """Persist manifest to Redis and update the in-memory recent-query log."""
    manifest_id: str = manifest["manifest_id"]
    _recent_query_ids.append(manifest["query_id"])
    if len(_recent_query_ids) > 200:
        _recent_query_ids.pop(0)

    if _redis:
        try:
            await _redis.set(
                f"manifest:{manifest_id}",
                json.dumps(manifest),
                ex=_MANIFEST_TTL,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis manifest save failed: %s", exc)


async def _load_manifest(manifest_id: str) -> dict[str, Any] | None:
    """Load manifest from Redis."""
    if _redis:
        try:
            raw = await _redis.get(f"manifest:{manifest_id}")
            if raw:
                return json.loads(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis manifest load failed: %s", exc)
    return None


def _build_manifest(
    result: Any,
    query_id: str,
    question: str,
    filters: dict[str, Any] | None,
    citations: list[Citation],
    answer_dict: dict[str, str],
) -> dict[str, Any]:
    return {
        "manifest_id": result.evidence_manifest_id,
        "query_id": query_id,
        "question": question,
        "filters": filters,
        "answer": answer_dict,
        "citations": [c.model_dump() for c in citations],
        "review_status": result.review_status,
        "review_feedback": result.review_feedback,
        "retrieved_doc_count": result.retrieved_doc_count,
        "feature_enriched_count": result.feature_enriched_count,
        "execution_timeline": getattr(result, "execution_timeline", []),
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
    }


def _result_to_response(result: Any, query_id: str) -> QueryResponse:
    answer_dict = result.answer or {}
    answer_block = AnswerBlock(
        background=answer_dict.get("background", ""),
        evidence=answer_dict.get("evidence", ""),
        statistics=answer_dict.get("statistics", ""),
        conclusion=answer_dict.get("conclusion", ""),
    )
    citations = [
        Citation(
            id=c.get("id", ""),
            type=c.get("type", ""),
            snippet=c.get("snippet", ""),
            score=float(c.get("score", 0.0)),
            title=c.get("title", ""),
            content=c.get("content", ""),
            iceberg_snapshot_ref=c.get("iceberg_snapshot_ref", ""),
        )
        for c in (result.citations or [])
    ]
    return QueryResponse(
        answer=answer_block,
        citations=citations,
        evidence_manifest_id=result.evidence_manifest_id,
        query_id=query_id,
        review_status=result.review_status,
        review_feedback=result.review_feedback,
        retrieved_doc_count=result.retrieved_doc_count,
        feature_enriched_count=result.feature_enriched_count,
    )


def _check_dq_citations(citations: list[Citation]) -> None:
    """DQ-UI-1: raise 422 if the answer has no citations (unsupported claims)."""
    if not citations:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "DQ-UI-1",
                "message": (
                    "Answer produced no citations. "
                    "The response cannot be returned without evidence backing. "
                    "Check that Phase 2 indexing has run and the retrieval-api "
                    "is healthy."
                ),
            },
        )


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "phase": "5"}


@app.post("/v1/query", response_model=QueryResponse)
async def query(request: QueryRequest) -> QueryResponse:
    """Submit a biomedical question via the durable Temporal EvidenceWorkflow."""
    if _temporal_client is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    from src.agent_worker.temporal.activities import AgentInput  # noqa: PLC0415
    from src.agent_worker.temporal.workflows import EvidenceWorkflow  # noqa: PLC0415

    query_id = str(uuid.uuid4())
    agent_input = AgentInput(
        question=request.question,
        query_id=query_id,
        filters=request.filters,
    )

    t0 = time.monotonic()
    try:
        handle = await _temporal_client.start_workflow(
            EvidenceWorkflow.run,
            agent_input,
            id=f"evidence-{query_id}",
            task_queue=_TASK_QUEUE,
        )
        result = await handle.result()
    except Exception as exc:
        QUERIES_TOTAL.labels(status="error").inc()
        logger.error("EvidenceWorkflow failed for query_id=%s: %s", query_id, exc)
        raise HTTPException(status_code=502, detail=f"Agent workflow failed: {exc}") from exc
    finally:
        QUERY_DURATION.observe(time.monotonic() - t0)

    response = _result_to_response(result, query_id)

    try:
        _check_dq_citations(response.citations)
    except HTTPException:
        DQ_VIOLATIONS_TOTAL.labels(rule="DQ-UI-1").inc()
        raise

    QUERIES_TOTAL.labels(status=result.review_status).inc()

    manifest = _build_manifest(
        result, query_id, request.question, request.filters,
        response.citations, response.answer.model_dump(),
    )
    await _save_manifest(manifest)
    return response


@app.post("/v1/query/stream")
async def query_stream(request: QueryRequest) -> EventSourceResponse:
    """Submit a question and stream per-node SSE events as the graph executes.

    Events
    ------
    ``step``
        Emitted after each LangGraph node completes.
        ``data`` is ``{"node": "<node_name>", "elapsed_ms": <int>}``.
    ``complete``
        Emitted once with the full :class:`QueryResponse` payload as JSON.
    ``error``
        Emitted if the graph raises an unhandled exception.
    """
    config = get_config()
    query_id = str(uuid.uuid4())
    question = request.question
    filters = request.filters

    async def _event_generator() -> AsyncGenerator[dict[str, Any], None]:
        from src.agent_worker.agents.graph import build_graph  # noqa: PLC0415
        from src.agent_worker.agents.state import AgentState  # noqa: PLC0415
        from src.agent_worker.temporal.activities import AgentOutput  # noqa: PLC0415

        graph = build_graph(
            retrieval_api_url=config.retrieval_api_url,
            feature_api_url=config.feature_api_url,
        )

        initial_state: AgentState = {
            "question": question,
            "filters": filters,
            "query_id": query_id,
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
        }

        # Run graph.stream() in a background thread; pass events via a queue
        event_q: _queue.Queue[tuple[str, Any]] = _queue.Queue()
        final_state: dict[str, Any] = {}
        timeline: list[dict[str, Any]] = []
        t0 = datetime.datetime.utcnow()

        def _run() -> None:
            try:
                state = dict(initial_state)
                for chunk in graph.stream(initial_state):
                    for node_name, updates in chunk.items():
                        elapsed_ms = int(
                            (datetime.datetime.utcnow() - t0).total_seconds() * 1000
                        )
                        timeline.append(
                            {
                                "step": node_name,
                                "started_at": datetime.datetime.utcnow().isoformat() + "Z",
                                "elapsed_ms": elapsed_ms,
                            }
                        )
                        state.update(updates)
                        event_q.put(("step", {"node": node_name, "elapsed_ms": elapsed_ms}))
                final_state.update(state)
            except Exception as exc:  # noqa: BLE001
                event_q.put(("error", str(exc)))
            finally:
                event_q.put(("done", None))

        thread = threading.Thread(target=_run, daemon=True)
        thread.start()

        while True:
            try:
                event_type, data = event_q.get_nowait()
            except _queue.Empty:
                await asyncio.sleep(0.02)
                continue

            if event_type == "done":
                break
            elif event_type == "error":
                yield {"event": "error", "data": json.dumps({"detail": data})}
                thread.join(timeout=5)
                return
            else:
                yield {"event": "step", "data": json.dumps(data)}

        thread.join(timeout=5)

        # Build and persist manifest
        docs = final_state.get("retrieved_docs", [])
        features = final_state.get("features", {})
        manifest_id = final_state.get("evidence_manifest_id", "")
        answer_dict = final_state.get("answer", {})
        raw_citations = final_state.get("citations", [])

        citations = [
            Citation(
                id=c.get("id", ""),
                type=c.get("type", ""),
                snippet=c.get("snippet", ""),
                score=float(c.get("score", 0.0)),
                title=c.get("title", ""),
                content=c.get("content", ""),
                iceberg_snapshot_ref=c.get("iceberg_snapshot_ref", ""),
            )
            for c in raw_citations
        ]

        response = QueryResponse(
            answer=AnswerBlock(
                background=answer_dict.get("background", ""),
                evidence=answer_dict.get("evidence", ""),
                statistics=answer_dict.get("statistics", ""),
                conclusion=answer_dict.get("conclusion", ""),
            ),
            citations=citations,
            evidence_manifest_id=manifest_id,
            query_id=query_id,
            review_status=final_state.get("review_status", "unknown"),
            review_feedback=final_state.get("review_feedback", ""),
            retrieved_doc_count=len(docs),
            feature_enriched_count=len(features),
        )

        # DQ-UI-1 check: emit error event instead of crashing the stream
        if not citations:
            yield {
                "event": "error",
                "data": json.dumps({
                    "error": "DQ-UI-1",
                    "message": "Answer produced no citations.",
                }),
            }
            return

        # Persist manifest with timeline
        manifest = {
            "manifest_id": manifest_id,
            "query_id": query_id,
            "question": question,
            "filters": filters,
            "answer": answer_dict,
            "citations": [c.model_dump() for c in citations],
            "review_status": final_state.get("review_status", "unknown"),
            "review_feedback": final_state.get("review_feedback", ""),
            "retrieved_doc_count": len(docs),
            "feature_enriched_count": len(features),
            "execution_timeline": timeline,
            "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        }
        await _save_manifest(manifest)

        yield {"event": "complete", "data": response.model_dump_json()}

    return EventSourceResponse(_event_generator())


@app.get("/v1/manifest/{manifest_id}")
async def get_manifest(manifest_id: str) -> dict[str, Any]:
    """Retrieve a stored evidence manifest by ID."""
    manifest = await _load_manifest(manifest_id)
    if manifest is None:
        raise HTTPException(
            status_code=404, detail=f"Manifest not found: {manifest_id}"
        )
    return manifest


@app.get("/v1/operator/queries")
async def operator_list_queries(
    _role: str = Depends(_require_operator),
) -> dict[str, Any]:
    """List the most recent query IDs.  Requires Operator role (``X-Role: operator``).

    Returns
    -------
    dict
        ``query_ids`` list (most recent last, capped at 200).
    """
    return {
        "query_ids": list(_recent_query_ids),
        "count": len(_recent_query_ids),
    }
