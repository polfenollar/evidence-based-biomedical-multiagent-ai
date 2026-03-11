"""Unit tests for the Lead Researcher agent node."""
from __future__ import annotations

import pytest

from src.agent_worker.agents.lead_researcher import lead_researcher


def _doc(doc_id: str = "PMID:1", score: float = 0.9, snippet: str = "A snippet.") -> dict:
    return {
        "doc_id": doc_id,
        "score": score,
        "title": f"Title of {doc_id}",
        "snippet": snippet,
        "source_type": "article",
        "iceberg_snapshot_ref": "snap-1",
        "indexing_run_id": "run-1",
    }


class TestLeadResearcher:
    def test_produces_answer_with_all_sections(self) -> None:
        state = {
            "question": "Does aspirin reduce MI risk?",
            "retrieved_docs": [_doc()],
            "features": {},
        }
        result = lead_researcher(state)
        answer = result["answer"]
        for key in ("background", "evidence", "statistics", "conclusion"):
            assert key in answer
            assert isinstance(answer[key], str)
            assert len(answer[key]) > 0

    def test_citations_match_retrieved_docs(self) -> None:
        docs = [_doc("PMID:1"), _doc("PMID:2")]
        state = {"question": "aspirin", "retrieved_docs": docs, "features": {}}
        result = lead_researcher(state)
        assert len(result["citations"]) == 2
        ids = {c["id"] for c in result["citations"]}
        assert ids == {"PMID:1", "PMID:2"}

    def test_no_docs_produces_insufficient_evidence_answer(self) -> None:
        state = {"question": "unknown query", "retrieved_docs": [], "features": {}}
        result = lead_researcher(state)
        assert "Insufficient" in result["answer"]["conclusion"] or \
               "No relevant" in result["answer"]["evidence"]

    def test_increments_revision_count(self) -> None:
        state = {
            "question": "aspirin",
            "retrieved_docs": [_doc()],
            "features": {},
            "revision_count": 1,
        }
        result = lead_researcher(state)
        assert result["revision_count"] == 2

    def test_resets_review_status_to_pending(self) -> None:
        state = {
            "question": "aspirin",
            "retrieved_docs": [_doc()],
            "features": {},
            "review_status": "rejected",
        }
        result = lead_researcher(state)
        assert result["review_status"] == "pending"

    def test_evidence_contains_doc_ids(self) -> None:
        docs = [_doc("PMID:42", snippet="Aspirin reduces platelet aggregation.")]
        state = {"question": "aspirin", "retrieved_docs": docs, "features": {}}
        result = lead_researcher(state)
        assert "PMID:42" in result["answer"]["evidence"]

    def test_statistics_from_features(self) -> None:
        docs = [_doc("PMID:1")]
        features = {"PMID:1": {"abstract_word_count": 200, "publication_year": 2021}}
        state = {"question": "aspirin", "retrieved_docs": docs, "features": features}
        result = lead_researcher(state)
        assert "200" in result["answer"]["statistics"] or "2021" in result["answer"]["statistics"]

    def test_conclusion_mentions_top_doc(self) -> None:
        docs = [_doc("PMID:99", score=0.95)]
        state = {"question": "aspirin", "retrieved_docs": docs, "features": {}}
        result = lead_researcher(state)
        assert "PMID:99" in result["answer"]["conclusion"]

    def test_citation_contains_expected_keys(self) -> None:
        state = {"question": "aspirin", "retrieved_docs": [_doc()], "features": {}}
        result = lead_researcher(state)
        c = result["citations"][0]
        for key in ("id", "type", "snippet", "score", "title", "iceberg_snapshot_ref"):
            assert key in c
