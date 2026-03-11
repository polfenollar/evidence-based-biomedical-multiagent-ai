"""Temporal activities for the biomedical multi-agent pipeline."""
from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from typing import Any

from temporalio import activity

from src.agent_worker.config import get_config


@dataclass
class AgentInput:
    question: str
    query_id: str
    filters: dict[str, Any] | None = None


@dataclass
class AgentOutput:
    query_id: str
    answer: dict[str, str]
    citations: list[dict[str, Any]]
    evidence_manifest_id: str
    review_status: str
    review_feedback: str
    retrieved_doc_count: int
    feature_enriched_count: int
    execution_timeline: list[dict[str, Any]] = field(default_factory=list)


@activity.defn
async def run_agent_graph_activity(input: AgentInput) -> AgentOutput:
    """Run the full LangGraph multi-agent graph for a single query.

    Uses ``graph.stream()`` so that per-node timing is recorded in the
    execution timeline stored in the returned :class:`AgentOutput`.

    Parameters
    ----------
    input:
        :class:`AgentInput` with the user question and optional filters.

    Returns
    -------
    AgentOutput
        Structured evidence answer, citations, and execution metadata.
    """
    from src.agent_worker.agents.graph import build_graph  # noqa: PLC0415
    from src.agent_worker.agents.state import AgentState  # noqa: PLC0415

    logger = activity.logger
    config = get_config()

    logger.info(
        "run_agent_graph_activity: query_id=%s question=%r",
        input.query_id,
        input.question[:80],
    )

    graph = build_graph(
        retrieval_api_url=config.retrieval_api_url,
        feature_api_url=config.feature_api_url,
    )

    initial_state: AgentState = {
        "question": input.question,
        "filters": input.filters,
        "query_id": input.query_id,
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

    # ── Langfuse trace (optional — no-ops if credentials absent) ──────────────
    langfuse_trace = None
    try:
        import os  # noqa: PLC0415
        if os.environ.get("LANGFUSE_PUBLIC_KEY"):
            from langfuse import Langfuse  # noqa: PLC0415
            _lf = Langfuse()
            langfuse_trace = _lf.trace(
                name="evidence-workflow",
                input={"question": input.question, "filters": input.filters},
                metadata={"query_id": input.query_id},
            )
    except Exception:  # noqa: BLE001
        langfuse_trace = None

    t0 = datetime.datetime.utcnow()
    final_state: dict[str, Any] = dict(initial_state)
    timeline: list[dict[str, Any]] = []

    for chunk in graph.stream(initial_state):
        for node_name, updates in chunk.items():
            step_start = datetime.datetime.utcnow()
            elapsed_ms = int((step_start - t0).total_seconds() * 1000)
            timeline.append(
                {
                    "step": node_name,
                    "started_at": step_start.isoformat() + "Z",
                    "elapsed_ms": elapsed_ms,
                }
            )
            # Emit per-node Langfuse span
            if langfuse_trace:
                try:
                    langfuse_trace.span(
                        name=node_name,
                        start_time=step_start,
                        input={"state_keys": list(updates.keys())},
                        metadata={"elapsed_ms": elapsed_ms},
                    )
                except Exception:  # noqa: BLE001
                    pass
            final_state.update(updates)

    if langfuse_trace:
        try:
            langfuse_trace.update(
                output={
                    "review_status": final_state.get("review_status"),
                    "citation_count": len(final_state.get("citations", [])),
                }
            )
        except Exception:  # noqa: BLE001
            pass

    docs = final_state.get("retrieved_docs", [])
    features = final_state.get("features", {})

    logger.info(
        "run_agent_graph_activity: query_id=%s docs=%d review=%s manifest=%s steps=%d",
        input.query_id,
        len(docs),
        final_state.get("review_status"),
        final_state.get("evidence_manifest_id"),
        len(timeline),
    )

    return AgentOutput(
        query_id=input.query_id,
        answer=final_state.get("answer", {}),
        citations=final_state.get("citations", []),
        evidence_manifest_id=final_state.get("evidence_manifest_id", ""),
        review_status=final_state.get("review_status", "unknown"),
        review_feedback=final_state.get("review_feedback", ""),
        retrieved_doc_count=len(docs),
        feature_enriched_count=len(features),
        execution_timeline=timeline,
    )
