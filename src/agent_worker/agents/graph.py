"""LangGraph multi-agent graph for evidence-based biomedical queries.

Graph structure
---------------
cmo_router
  → medical_librarian
    → clinical_biostatistician
      → lead_researcher
        → peer_reviewer
          ─ approved ──────────────→ finalize → END
          ─ rejected + retries left → lead_researcher (retry loop)
          ─ rejected + retries gone → finalize → END
"""
from __future__ import annotations

import uuid
from typing import Any

from langgraph.graph import END, StateGraph

from .clinical_biostatistician import make_clinical_biostatistician
from .cmo_router import cmo_router
from .lead_researcher import lead_researcher
from .medical_librarian import make_medical_librarian
from .peer_reviewer import peer_reviewer
from .state import AgentState

_MAX_REVISIONS = 2


def _finalize(state: AgentState) -> dict[str, Any]:
    """Assign a stable evidence manifest ID and close the graph run."""
    return {"evidence_manifest_id": str(uuid.uuid4())}


def _route_after_review(state: AgentState) -> str:
    """Conditional edge: retry researcher or proceed to finalize."""
    if state.get("review_status") == "approved":
        return "finalize"
    if (state.get("revision_count", 0)) >= _MAX_REVISIONS:
        return "finalize"
    return "lead_researcher"


def build_graph(retrieval_api_url: str, feature_api_url: str) -> Any:
    """Compile and return the runnable LangGraph agent graph.

    Parameters
    ----------
    retrieval_api_url:
        Base URL of the retrieval service.
    feature_api_url:
        Base URL of the feature service.

    Returns
    -------
    CompiledGraph
        A runnable LangGraph graph that accepts an :class:`AgentState` dict
        and returns a completed :class:`AgentState` dict.
    """
    graph: StateGraph = StateGraph(AgentState)

    graph.add_node("cmo_router", cmo_router)
    graph.add_node("medical_librarian", make_medical_librarian(retrieval_api_url))
    graph.add_node(
        "clinical_biostatistician", make_clinical_biostatistician(feature_api_url)
    )
    graph.add_node("lead_researcher", lead_researcher)
    graph.add_node("peer_reviewer", peer_reviewer)
    graph.add_node("finalize", _finalize)

    graph.set_entry_point("cmo_router")
    graph.add_edge("cmo_router", "medical_librarian")
    graph.add_edge("medical_librarian", "clinical_biostatistician")
    graph.add_edge("clinical_biostatistician", "lead_researcher")
    graph.add_edge("lead_researcher", "peer_reviewer")
    graph.add_conditional_edges(
        "peer_reviewer",
        _route_after_review,
        {"finalize": "finalize", "lead_researcher": "lead_researcher"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()
