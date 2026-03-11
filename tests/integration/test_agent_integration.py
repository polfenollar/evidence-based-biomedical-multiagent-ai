"""Integration tests for the multi-agent pipeline.

Requires:
- retrieval-api running at RETRIEVAL_API_URL (default http://localhost:8001)
- feature-api running at FEATURE_API_URL (default http://localhost:8002)
- Both services must have data already indexed (Phase 2 + Phase 3 complete)

Run with:
    pytest -m integration tests/integration/test_agent_integration.py
"""
from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.integration

_RETRIEVAL_API_URL = os.environ.get("RETRIEVAL_API_URL", "http://localhost:8001")
_FEATURE_API_URL = os.environ.get("FEATURE_API_URL", "http://localhost:8002")


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def graph():
    from src.agent_worker.agents.graph import build_graph

    return build_graph(
        retrieval_api_url=_RETRIEVAL_API_URL,
        feature_api_url=_FEATURE_API_URL,
    )


def _initial_state(question: str, filters: dict | None = None) -> dict:
    import uuid

    return {
        "question": question,
        "filters": filters,
        "query_id": str(uuid.uuid4()),
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


# ── Tests ──────────────────────────────────────────────────────────────────────


def test_graph_returns_answer_and_citations(graph) -> None:
    """Full graph run should produce a non-empty answer with citations."""
    final = graph.invoke(_initial_state("cardiovascular effects of aspirin"))

    assert final["answer"], "answer should be non-empty"
    for section in ("background", "evidence", "statistics", "conclusion"):
        assert final["answer"].get(section), f"answer.{section} should be non-empty"

    assert isinstance(final["citations"], list)
    # May be 0 if retrieval-api has no indexed data, but should not error
    assert "evidence_manifest_id" in final
    assert final["evidence_manifest_id"] != ""


def test_graph_retrieves_relevant_docs(graph) -> None:
    """Librarian should return at least one doc for a query matching indexed data."""
    final = graph.invoke(_initial_state("aspirin cardiovascular prevention"))

    # If Phase 2 data is present, we should get at least one result
    assert len(final.get("retrieved_docs", [])) > 0, (
        "Expected at least one retrieved document — "
        "check that Phase 2 indexing has run and retrieval-api is healthy"
    )


def test_graph_review_status_is_terminal(graph) -> None:
    """review_status must be 'approved' or 'rejected' (never 'pending') after graph run."""
    final = graph.invoke(_initial_state("metformin diabetes treatment"))
    assert final["review_status"] in {"approved", "rejected"}


def test_graph_with_source_type_filter(graph) -> None:
    """Applying a source_type filter should not cause errors."""
    final = graph.invoke(
        _initial_state(
            "clinical trial on aspirin",
            filters={"source_type": "trial"},
        )
    )
    assert "evidence_manifest_id" in final


def test_graph_citations_have_doc_ids(graph) -> None:
    """Every citation must have a non-empty 'id' field."""
    final = graph.invoke(_initial_state("aspirin coronary artery disease"))
    for citation in final.get("citations", []):
        assert citation.get("id"), f"Citation missing id: {citation}"


def test_graph_feature_enrichment_for_known_pmid(graph) -> None:
    """If retrieval returns articles, biostatistician should attempt feature lookup."""
    final = graph.invoke(_initial_state("aspirin cardiovascular outcomes"))
    # features may be empty if no PMIDs match the feature store; that is acceptable
    # but the key must exist in the final state
    assert "features" in final
    assert isinstance(final["features"], dict)


def test_reviewer_approves_when_evidence_present(graph) -> None:
    """With real retrieved docs and snippets, reviewer should approve."""
    final = graph.invoke(_initial_state("aspirin cardiovascular prevention"))
    if final.get("retrieved_docs"):
        # If docs were found, snippets should be non-empty → approved
        assert final["review_status"] == "approved", (
            f"Reviewer rejected with: {final.get('review_feedback')}"
        )
