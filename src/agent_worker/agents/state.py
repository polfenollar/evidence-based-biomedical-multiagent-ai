"""Shared state type for the LangGraph multi-agent graph."""
from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    """Mutable state passed between agent nodes in the LangGraph graph.

    Fields are populated incrementally as each node runs.  ``total=False``
    means no field is required at construction time; each node is responsible
    for writing only the fields it owns.
    """

    # ── Input ──────────────────────────────────────────────────────────────────
    question: str
    filters: dict[str, Any] | None
    query_id: str

    # ── CMO Router ─────────────────────────────────────────────────────────────
    search_query: str
    search_limit: int

    # ── Medical Librarian ──────────────────────────────────────────────────────
    retrieved_docs: list[dict[str, Any]]

    # ── Clinical Biostatistician ───────────────────────────────────────────────
    features: dict[str, dict[str, Any]]

    # ── Lead Researcher ────────────────────────────────────────────────────────
    answer: dict[str, str]          # background, evidence, statistics, conclusion
    citations: list[dict[str, Any]]
    revision_count: int

    # ── Peer Reviewer ──────────────────────────────────────────────────────────
    review_status: str              # "pending" | "approved" | "rejected"
    review_feedback: str

    # ── Finalize ───────────────────────────────────────────────────────────────
    evidence_manifest_id: str
