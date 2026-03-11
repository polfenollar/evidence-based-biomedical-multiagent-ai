"""Unit tests for the Peer Reviewer agent node."""
from __future__ import annotations

import pytest

from src.agent_worker.agents.peer_reviewer import peer_reviewer


def _good_answer() -> dict:
    return {
        "background": "Background text.",
        "evidence": "Evidence text.",
        "statistics": "Statistics text.",
        "conclusion": "Conclusion text.",
    }


def _good_citation(cid: str = "PMID:1", snippet: str = "Some snippet.") -> dict:
    return {
        "id": cid,
        "type": "article",
        "snippet": snippet,
        "score": 0.9,
        "title": "Title",
    }


class TestPeerReviewer:
    def test_approves_valid_answer(self) -> None:
        state = {
            "answer": _good_answer(),
            "citations": [_good_citation()],
        }
        result = peer_reviewer(state)
        assert result["review_status"] == "approved"
        assert result["review_feedback"] == ""

    def test_rejects_when_no_citations(self) -> None:
        state = {"answer": _good_answer(), "citations": []}
        result = peer_reviewer(state)
        assert result["review_status"] == "rejected"
        assert "No citations" in result["review_feedback"]

    def test_rejects_when_citation_has_empty_snippet(self) -> None:
        bad_citation = _good_citation(snippet="")
        state = {
            "answer": _good_answer(),
            "citations": [bad_citation],
        }
        result = peer_reviewer(state)
        assert result["review_status"] == "rejected"
        assert "empty snippet" in result["review_feedback"].lower()

    def test_rejects_when_citation_has_whitespace_only_snippet(self) -> None:
        bad_citation = _good_citation(snippet="   ")
        state = {
            "answer": _good_answer(),
            "citations": [bad_citation],
        }
        result = peer_reviewer(state)
        assert result["review_status"] == "rejected"

    def test_rejects_when_answer_section_missing(self) -> None:
        bad_answer = _good_answer()
        del bad_answer["conclusion"]
        state = {
            "answer": bad_answer,
            "citations": [_good_citation()],
        }
        result = peer_reviewer(state)
        assert result["review_status"] == "rejected"
        assert "conclusion" in result["review_feedback"]

    def test_rejects_when_answer_section_empty(self) -> None:
        bad_answer = _good_answer()
        bad_answer["evidence"] = ""
        state = {
            "answer": bad_answer,
            "citations": [_good_citation()],
        }
        result = peer_reviewer(state)
        assert result["review_status"] == "rejected"

    def test_approves_multiple_citations(self) -> None:
        citations = [_good_citation(f"PMID:{i}", snippet=f"Snippet {i}.") for i in range(3)]
        state = {"answer": _good_answer(), "citations": citations}
        result = peer_reviewer(state)
        assert result["review_status"] == "approved"

    def test_rejected_feedback_names_missing_section(self) -> None:
        bad_answer = _good_answer()
        bad_answer["statistics"] = ""
        state = {"answer": bad_answer, "citations": [_good_citation()]}
        result = peer_reviewer(state)
        assert "statistics" in result["review_feedback"]
