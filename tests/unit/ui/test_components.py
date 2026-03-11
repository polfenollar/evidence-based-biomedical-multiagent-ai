"""Unit tests for UI helper functions (no Streamlit required)."""
from __future__ import annotations

import json

import pytest

from src.ui.components import (
    check_response_has_citations,
    format_answer_sections,
    format_aggregate_summary,
    format_citation_badge,
    format_citation_detail,
    format_timeline_row,
    format_timeline_table,
    node_display_name,
    parse_sse_event,
)


def _citation(cid: str = "PMID:1", ctype: str = "article", snippet: str = "Snippet.", content: str = "Full content.") -> dict:
    return {
        "id": cid,
        "type": ctype,
        "snippet": snippet,
        "content": content,
        "score": 0.9,
        "title": "Title",
        "iceberg_snapshot_ref": "snap-1",
    }


class TestFormatCitationBadge:
    def test_includes_type_and_id(self) -> None:
        badge = format_citation_badge(_citation("PMID:99"))
        assert "article" in badge
        assert "PMID:99" in badge

    def test_trial_type(self) -> None:
        badge = format_citation_badge({"id": "NCT001", "type": "trial"})
        assert "trial" in badge
        assert "NCT001" in badge

    def test_missing_fields_fallback(self) -> None:
        badge = format_citation_badge({})
        assert "unknown" in badge or "?" in badge


class TestFormatCitationDetail:
    def test_contains_badge(self) -> None:
        detail = format_citation_detail(_citation("PMID:5"))
        assert "PMID:5" in detail

    def test_contains_score(self) -> None:
        detail = format_citation_detail(_citation())
        assert "0.900" in detail or "0.9" in detail

    def test_contains_title(self) -> None:
        detail = format_citation_detail(_citation())
        assert "Title" in detail

    def test_contains_snippet(self) -> None:
        detail = format_citation_detail(_citation(snippet="Important finding."))
        assert "Important finding." in detail

    def test_contains_content(self) -> None:
        detail = format_citation_detail(_citation(content="This is the full text."))
        assert "Full Content:" in detail
        assert "This is the full text." in detail

    def test_contains_snapshot_ref(self) -> None:
        detail = format_citation_detail(_citation())
        assert "snap-1" in detail


class TestFormatTimeline:
    def test_row_has_correct_keys(self) -> None:
        row = format_timeline_row({"step": "cmo_router", "elapsed_ms": 5, "started_at": "2024-01-01T00:00:00Z"})
        assert row["Node"] == "cmo_router"
        assert row["Elapsed (ms)"] == 5
        assert "Started At" in row

    def test_table_length_matches_input(self) -> None:
        timeline = [
            {"step": "cmo_router", "elapsed_ms": 2, "started_at": ""},
            {"step": "medical_librarian", "elapsed_ms": 100, "started_at": ""},
        ]
        rows = format_timeline_table(timeline)
        assert len(rows) == 2

    def test_empty_timeline_returns_empty(self) -> None:
        assert format_timeline_table([]) == []


class TestFormatAnswerSections:
    def test_returns_four_sections(self) -> None:
        answer = {
            "background": "BG",
            "evidence": "EV",
            "statistics": "ST",
            "conclusion": "CO",
        }
        sections = format_answer_sections(answer)
        assert len(sections) == 4

    def test_section_labels(self) -> None:
        answer = {"background": "B", "evidence": "E", "statistics": "S", "conclusion": "C"}
        labels = [label for label, _ in format_answer_sections(answer)]
        assert "Background" in labels
        assert "Conclusion" in labels

    def test_section_order_background_first(self) -> None:
        answer = {"background": "B", "evidence": "E", "statistics": "S", "conclusion": "C"}
        sections = format_answer_sections(answer)
        assert sections[0][0] == "Background"
        assert sections[-1][0] == "Conclusion"

    def test_missing_key_returns_empty_string(self) -> None:
        sections = format_answer_sections({})
        for _, text in sections:
            assert text == ""


class TestNodeDisplayName:
    def test_known_nodes_have_labels(self) -> None:
        assert "CMO" in node_display_name("cmo_router")
        assert "Librarian" in node_display_name("medical_librarian")
        assert "Biostatistician" in node_display_name("clinical_biostatistician")
        assert "Researcher" in node_display_name("lead_researcher")
        assert "Reviewer" in node_display_name("peer_reviewer")
        assert "Finalize" in node_display_name("finalize")

    def test_unknown_node_returns_itself(self) -> None:
        assert node_display_name("mystery_node") == "mystery_node"


class TestParseSseEvent:
    def test_parses_data_line(self) -> None:
        line = 'data: {"node": "cmo_router", "elapsed_ms": 5}'
        result = parse_sse_event(line)
        assert result is not None
        assert result["node"] == "cmo_router"

    def test_non_data_line_returns_none(self) -> None:
        assert parse_sse_event("event: step") is None
        assert parse_sse_event("") is None
        assert parse_sse_event(": keep-alive") is None

    def test_malformed_json_returns_none(self) -> None:
        assert parse_sse_event("data: {not valid json}") is None

    def test_empty_data_line_returns_none(self) -> None:
        # data: with empty object is valid
        result = parse_sse_event("data: {}")
        assert result == {}


class TestCheckResponseHasCitations:
    def test_returns_none_when_citations_present(self) -> None:
        response = {"citations": [{"id": "PMID:1", "snippet": "s"}]}
        assert check_response_has_citations(response) is None

    def test_returns_error_when_empty_citations(self) -> None:
        response = {"citations": []}
        error = check_response_has_citations(response)
        assert error is not None
        assert "DQ-UI-1" in error

    def test_returns_error_when_citations_absent(self) -> None:
        response = {}
        error = check_response_has_citations(response)
        assert error is not None


class TestFormatAggregateSummary:
    def test_aggregates_multiple_snippets(self) -> None:
        citations = [
            {"id": "DOC1", "title": "Title 1", "snippet": "Snippet 1.", "score": 0.9},
            {"id": "DOC2", "title": "Title 2", "snippet": "Snippet 2.", "score": 0.8},
        ]
        summary = format_aggregate_summary(citations)
        assert "Snippet 1." in summary
        assert "Snippet 2." in summary
        assert "DOC1" in summary
        assert "Title 2" in summary

    def test_empty_citations_returns_fallback(self) -> None:
        assert "No documentation content found" in format_aggregate_summary([])

    def test_citations_without_snippets(self) -> None:
        citations = [{"id": "DOC1", "score": 0.9}]
        assert "No substantive snippets found" in format_aggregate_summary(citations)

    def test_sorts_by_score(self) -> None:
        citations = [
            {"id": "LOW", "snippet": "Low.", "score": 0.1},
            {"id": "HIGH", "snippet": "High.", "score": 0.9},
        ]
        summary = format_aggregate_summary(citations)
        # HIGH should appear before LOW in the summary
        assert summary.find("HIGH") < summary.find("LOW")
