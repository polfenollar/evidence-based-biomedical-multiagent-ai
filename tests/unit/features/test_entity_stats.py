"""Unit tests for entity_stats feature computation functions.

All tests are pure-Python — no running infrastructure required.
"""
from __future__ import annotations

import pytest

from src.feature_worker.features.entity_stats import (
    compute_article_stats,
    compute_article_stats_batch,
    compute_trial_stats,
    compute_trial_stats_batch,
)

# ── Fixtures / shared data ─────────────────────────────────────────────────────

_VALID_ARTICLE = {
    "pmid": "38000001",
    "title": "Machine learning for cardiovascular risk prediction",
    "abstract": "An abstract describing the study in detail.",
    "publication_date": "2024-01-15",
    "journal": "Diabetes Care",
    "snapshot_ref": "snap-001",
}

_VALID_TRIAL = {
    "nct_id": "NCT00000001",
    "sample_size": 250,
    "primary_outcomes": "Reduction in HbA1c at 12 weeks",
    "status": "Completed",
    "conditions": "diabetes, hypertension, obesity",
    "snapshot_ref": "snap-001",
}


# ── Article stats tests ────────────────────────────────────────────────────────


class TestComputeArticleStatsValid:
    def test_title_word_count(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["title_word_count"] == 6

    def test_abstract_word_count(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["abstract_word_count"] == 7

    def test_publication_year_full_date(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["publication_year"] == 2024

    def test_has_abstract_is_one(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["has_abstract"] == 1

    def test_journal_encoded_passthrough(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["journal_encoded"] == "Diabetes Care"

    def test_snapshot_ref_preserved(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["snapshot_ref"] == "snap-001"

    def test_pmid_preserved(self) -> None:
        result = compute_article_stats(_VALID_ARTICLE)
        assert result["pmid"] == "38000001"


class TestComputeArticleStatsNullAbstract:
    def test_abstract_word_count_is_zero(self) -> None:
        record = {**_VALID_ARTICLE, "abstract": None}
        result = compute_article_stats(record)
        assert result["abstract_word_count"] == 0

    def test_has_abstract_is_zero(self) -> None:
        record = {**_VALID_ARTICLE, "abstract": None}
        result = compute_article_stats(record)
        assert result["has_abstract"] == 0

    def test_empty_abstract_word_count_is_zero(self) -> None:
        record = {**_VALID_ARTICLE, "abstract": ""}
        result = compute_article_stats(record)
        assert result["abstract_word_count"] == 0

    def test_empty_abstract_has_abstract_is_zero(self) -> None:
        record = {**_VALID_ARTICLE, "abstract": "   "}
        result = compute_article_stats(record)
        assert result["has_abstract"] == 0


class TestComputeArticleStatsDates:
    def test_date_full_yyyy_mm_dd(self) -> None:
        record = {**_VALID_ARTICLE, "publication_date": "2024-01-15"}
        result = compute_article_stats(record)
        assert result["publication_year"] == 2024

    def test_date_yyyy_mm(self) -> None:
        record = {**_VALID_ARTICLE, "publication_date": "2024-03"}
        result = compute_article_stats(record)
        assert result["publication_year"] == 2024

    def test_date_yyyy_only(self) -> None:
        record = {**_VALID_ARTICLE, "publication_date": "2021"}
        result = compute_article_stats(record)
        assert result["publication_year"] == 2021

    def test_date_invalid_returns_zero(self) -> None:
        record = {**_VALID_ARTICLE, "publication_date": "not-a-date"}
        result = compute_article_stats(record)
        assert result["publication_year"] == 0

    def test_date_none_returns_zero(self) -> None:
        record = {**_VALID_ARTICLE, "publication_date": None}
        result = compute_article_stats(record)
        assert result["publication_year"] == 0


# ── Trial stats tests ──────────────────────────────────────────────────────────


class TestComputeTrialStatsValid:
    def test_sample_size_preserved(self) -> None:
        result = compute_trial_stats(_VALID_TRIAL)
        assert result["sample_size"] == 250

    def test_has_outcomes_is_one(self) -> None:
        result = compute_trial_stats(_VALID_TRIAL)
        assert result["has_outcomes"] == 1

    def test_status_encoded_passthrough(self) -> None:
        result = compute_trial_stats(_VALID_TRIAL)
        assert result["status_encoded"] == "Completed"

    def test_condition_count_three(self) -> None:
        result = compute_trial_stats(_VALID_TRIAL)
        assert result["condition_count"] == 3

    def test_snapshot_ref_preserved(self) -> None:
        result = compute_trial_stats(_VALID_TRIAL)
        assert result["snapshot_ref"] == "snap-001"

    def test_nct_id_preserved(self) -> None:
        result = compute_trial_stats(_VALID_TRIAL)
        assert result["nct_id"] == "NCT00000001"


class TestComputeTrialStatsNullFields:
    def test_null_sample_size_returns_zero(self) -> None:
        record = {**_VALID_TRIAL, "sample_size": None}
        result = compute_trial_stats(record)
        assert result["sample_size"] == 0

    def test_null_primary_outcomes_has_outcomes_zero(self) -> None:
        record = {**_VALID_TRIAL, "primary_outcomes": None}
        result = compute_trial_stats(record)
        assert result["has_outcomes"] == 0

    def test_empty_primary_outcomes_has_outcomes_zero(self) -> None:
        record = {**_VALID_TRIAL, "primary_outcomes": ""}
        result = compute_trial_stats(record)
        assert result["has_outcomes"] == 0

    def test_null_conditions_count_zero(self) -> None:
        record = {**_VALID_TRIAL, "conditions": None}
        result = compute_trial_stats(record)
        assert result["condition_count"] == 0

    def test_empty_conditions_count_zero(self) -> None:
        record = {**_VALID_TRIAL, "conditions": ""}
        result = compute_trial_stats(record)
        assert result["condition_count"] == 0


class TestComputeTrialStatsConditionCounting:
    def test_three_conditions(self) -> None:
        record = {**_VALID_TRIAL, "conditions": "diabetes, hypertension, obesity"}
        result = compute_trial_stats(record)
        assert result["condition_count"] == 3

    def test_single_condition(self) -> None:
        record = {**_VALID_TRIAL, "conditions": "diabetes"}
        result = compute_trial_stats(record)
        assert result["condition_count"] == 1

    def test_conditions_with_extra_spaces(self) -> None:
        record = {**_VALID_TRIAL, "conditions": " diabetes ,  obesity "}
        result = compute_trial_stats(record)
        assert result["condition_count"] == 2


# ── Batch function tests ───────────────────────────────────────────────────────


class TestBatchFunctions:
    def test_compute_article_stats_batch_multiple(self) -> None:
        records = [
            {**_VALID_ARTICLE, "pmid": f"3800000{i}", "title": f"Title {i}"}
            for i in range(3)
        ]
        results = compute_article_stats_batch(records)
        assert len(results) == 3
        assert results[0]["pmid"] == "38000000"
        assert results[2]["pmid"] == "38000002"

    def test_compute_article_stats_batch_empty(self) -> None:
        results = compute_article_stats_batch([])
        assert results == []

    def test_compute_trial_stats_batch_multiple(self) -> None:
        records = [
            {**_VALID_TRIAL, "nct_id": f"NCT0000000{i}", "sample_size": i * 100}
            for i in range(4)
        ]
        results = compute_trial_stats_batch(records)
        assert len(results) == 4
        assert results[1]["sample_size"] == 100

    def test_compute_trial_stats_batch_empty(self) -> None:
        results = compute_trial_stats_batch([])
        assert results == []
