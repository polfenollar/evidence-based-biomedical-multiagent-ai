"""Unit tests for the CMO Router agent node."""
from __future__ import annotations

import pytest

from src.agent_worker.agents.cmo_router import cmo_router


class TestCmoRouter:
    def test_returns_search_query(self) -> None:
        state = {"question": "What is the effect of aspirin on heart disease?"}
        result = cmo_router(state)
        assert "search_query" in result
        assert isinstance(result["search_query"], str)
        assert len(result["search_query"]) > 0

    def test_search_query_strips_stop_words(self) -> None:
        state = {"question": "What is the effect of aspirin on heart disease?"}
        result = cmo_router(state)
        # Common stop words should not dominate the query
        search_terms = result["search_query"].split()
        assert "aspirin" in search_terms or "heart" in search_terms

    def test_returns_search_limit(self) -> None:
        state = {"question": "aspirin trial"}
        result = cmo_router(state)
        assert result["search_limit"] == 5

    def test_detects_trial_source_type(self) -> None:
        state = {"question": "randomized clinical trial of metformin in diabetes"}
        result = cmo_router(state)
        filters = result.get("filters") or {}
        assert filters.get("source_type") == "trial"

    def test_detects_article_source_type(self) -> None:
        state = {"question": "research article on cardiovascular outcomes aspirin"}
        result = cmo_router(state)
        filters = result.get("filters") or {}
        assert filters.get("source_type") == "article"

    def test_respects_user_provided_source_type(self) -> None:
        state = {
            "question": "trial on aspirin",
            "filters": {"source_type": "article"},
        }
        result = cmo_router(state)
        filters = result.get("filters") or {}
        # User's explicit choice should not be overwritten
        assert filters["source_type"] == "article"

    def test_no_filter_when_ambiguous(self) -> None:
        state = {"question": "aspirin cardiovascular outcomes"}
        result = cmo_router(state)
        filters = result.get("filters")
        # No strong trial/article keywords → filters may be None or empty
        if filters is not None:
            assert "source_type" not in filters

    def test_empty_question_returns_fallback(self) -> None:
        state = {"question": ""}
        result = cmo_router(state)
        assert "search_query" in result  # should not raise

    def test_preserves_additional_user_filters(self) -> None:
        state = {
            "question": "cardiovascular aspirin",
            "filters": {"date_from": "2020-01-01"},
        }
        result = cmo_router(state)
        filters = result.get("filters") or {}
        assert filters.get("date_from") == "2020-01-01"
