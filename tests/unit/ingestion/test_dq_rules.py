"""Unit tests for DQ rules."""
from __future__ import annotations

import pytest

from src.ingestion_worker.dq.rules import (
    DQResult,
    check_nct_id_present,
    check_nct_id_unique,
    check_pmid_present,
    check_pmid_unique,
    check_provenance_fields,
    check_title_nonempty,
    has_blocking_failures,
    run_clinicaltrials_dq,
    run_pubmed_dq,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _pubmed_record(pmid: str | None = "38000001", title: str = "Valid Title") -> dict:
    return {
        "pmid": pmid,
        "title": title,
        "abstract": "An abstract.",
        "authors": ["Author A"],
        "publication_date": "2024-01-01",
        "journal": "Test Journal",
        "source_name": "pubmed",
        "source_version": "2024-01",
        "source_uri": "ftp://example.com/sample.xml",
        "ingested_at": "2024-03-01T00:00:00+00:00",
        "ingestion_run_id": "run-001",
        "pipeline_version": "0.1.0",
    }


def _ct_record(nct_id: str | None = "NCT05000001") -> dict:
    return {
        "nct_id": nct_id,
        "brief_title": "A Clinical Trial",
        "conditions": ["Condition A"],
        "interventions": ["Drug A"],
        "primary_outcomes": ["Outcome A"],
        "sample_size": 100,
        "status": "RECRUITING",
        "start_date": "2023-01-01",
        "completion_date": "2025-01-01",
        "source_name": "clinicaltrials",
        "source_version": "2024-01",
        "source_uri": "https://clinicaltrials.gov/sample.zip",
        "ingested_at": "2024-03-01T00:00:00+00:00",
        "ingestion_run_id": "run-001",
        "pipeline_version": "0.1.0",
    }


# ── check_pmid_present ────────────────────────────────────────────────────────

class TestCheckPmidPresent:
    def test_pmid_present_pass(self) -> None:
        result = check_pmid_present(_pubmed_record(pmid="38000001"))
        assert result.outcome == "PASS"
        assert result.rule_id == "DQ-PUB-RAW-1"

    def test_pmid_present_fail_null(self) -> None:
        result = check_pmid_present(_pubmed_record(pmid=None))
        assert result.outcome == "FAIL"
        assert result.rule_id == "DQ-PUB-RAW-1"

    def test_pmid_present_fail_empty(self) -> None:
        result = check_pmid_present(_pubmed_record(pmid=""))
        assert result.outcome == "FAIL"

    def test_pmid_present_fail_whitespace(self) -> None:
        result = check_pmid_present(_pubmed_record(pmid="   "))
        assert result.outcome == "FAIL"


# ── check_pmid_unique ─────────────────────────────────────────────────────────

class TestCheckPmidUnique:
    def test_pmid_unique_pass(self) -> None:
        records = [_pubmed_record(pmid=str(i)) for i in range(5)]
        result = check_pmid_unique(records)
        assert result.outcome == "PASS"
        assert result.rule_id == "DQ-PUB-CUR-1"

    def test_pmid_unique_fail(self) -> None:
        records = [_pubmed_record(pmid="38000001"), _pubmed_record(pmid="38000001")]
        result = check_pmid_unique(records)
        assert result.outcome == "FAIL"
        assert "38000001" in result.failed_ids

    def test_pmid_unique_empty_batch(self) -> None:
        result = check_pmid_unique([])
        assert result.outcome == "PASS"


# ── check_title_nonempty ──────────────────────────────────────────────────────

class TestCheckTitleNonempty:
    def test_title_nonempty_pass(self) -> None:
        result = check_title_nonempty(_pubmed_record(title="A real title"))
        assert result.outcome == "PASS"
        assert result.rule_id == "DQ-PUB-CUR-2"

    def test_title_nonempty_fail_empty(self) -> None:
        result = check_title_nonempty(_pubmed_record(title=""))
        assert result.outcome == "FAIL"

    def test_title_nonempty_fail_whitespace(self) -> None:
        result = check_title_nonempty(_pubmed_record(title="   "))
        assert result.outcome == "FAIL"

    def test_title_nonempty_fail_none(self) -> None:
        record = _pubmed_record()
        record["title"] = None
        result = check_title_nonempty(record)
        assert result.outcome == "FAIL"


# ── check_provenance_fields ───────────────────────────────────────────────────

class TestCheckProvenanceFields:
    def test_provenance_fields_pass(self) -> None:
        result = check_provenance_fields(_pubmed_record())
        assert result.outcome == "PASS"
        assert result.rule_id == "DQ-P1"

    def test_provenance_fields_fail_missing_run_id(self) -> None:
        record = _pubmed_record()
        del record["ingestion_run_id"]
        result = check_provenance_fields(record)
        assert result.outcome == "FAIL"

    def test_provenance_fields_fail_empty_source_name(self) -> None:
        record = _pubmed_record()
        record["source_name"] = ""
        result = check_provenance_fields(record)
        assert result.outcome == "FAIL"

    def test_provenance_fields_fail_null_ingested_at(self) -> None:
        record = _pubmed_record()
        record["ingested_at"] = None
        result = check_provenance_fields(record)
        assert result.outcome == "FAIL"


# ── check_nct_id_present ──────────────────────────────────────────────────────

class TestCheckNctIdPresent:
    def test_nct_id_present_pass(self) -> None:
        result = check_nct_id_present(_ct_record(nct_id="NCT05000001"))
        assert result.outcome == "PASS"
        assert result.rule_id == "DQ-CT-RAW-1"

    def test_nct_id_present_fail(self) -> None:
        result = check_nct_id_present(_ct_record(nct_id=None))
        assert result.outcome == "FAIL"
        assert result.rule_id == "DQ-CT-RAW-1"

    def test_nct_id_present_fail_empty(self) -> None:
        result = check_nct_id_present(_ct_record(nct_id=""))
        assert result.outcome == "FAIL"


# ── check_nct_id_unique ───────────────────────────────────────────────────────

class TestCheckNctIdUnique:
    def test_nct_id_unique_pass(self) -> None:
        records = [_ct_record(nct_id=f"NCT0500000{i}") for i in range(4)]
        result = check_nct_id_unique(records)
        assert result.outcome == "PASS"
        assert result.rule_id == "DQ-CT-CUR-1"

    def test_nct_id_unique_fail(self) -> None:
        records = [_ct_record(nct_id="NCT05000001"), _ct_record(nct_id="NCT05000001")]
        result = check_nct_id_unique(records)
        assert result.outcome == "FAIL"
        assert "NCT05000001" in result.failed_ids


# ── has_blocking_failures ─────────────────────────────────────────────────────

class TestHasBlockingFailures:
    def test_has_blocking_failures_true(self) -> None:
        results = [
            DQResult(rule_id="DQ-PUB-RAW-1", outcome="PASS", message="ok"),
            DQResult(rule_id="DQ-PUB-CUR-1", outcome="FAIL", message="dup"),
        ]
        assert has_blocking_failures(results) is True

    def test_has_blocking_failures_false(self) -> None:
        results = [
            DQResult(rule_id="DQ-PUB-RAW-1", outcome="PASS", message="ok"),
            DQResult(rule_id="DQ-PUB-CUR-2", outcome="WARN", message="warn"),
        ]
        assert has_blocking_failures(results) is False

    def test_has_blocking_failures_empty(self) -> None:
        assert has_blocking_failures([]) is False


# ── run_pubmed_dq ─────────────────────────────────────────────────────────────

class TestRunPubmedDq:
    def test_run_pubmed_dq_clean_data(self) -> None:
        records = [_pubmed_record(pmid=str(i), title=f"Title {i}") for i in range(1, 6)]
        results = run_pubmed_dq(records)
        assert not has_blocking_failures(results)

    def test_run_pubmed_dq_dirty_data_null_pmid(self) -> None:
        records = [_pubmed_record(pmid=None)]
        results = run_pubmed_dq(records)
        assert has_blocking_failures(results)

    def test_run_pubmed_dq_dirty_data_empty_title(self) -> None:
        records = [_pubmed_record(title="")]
        results = run_pubmed_dq(records)
        assert has_blocking_failures(results)

    def test_run_pubmed_dq_dirty_data_duplicate_pmids(self) -> None:
        records = [_pubmed_record(pmid="DUP"), _pubmed_record(pmid="DUP")]
        results = run_pubmed_dq(records)
        assert has_blocking_failures(results)


# ── run_clinicaltrials_dq ─────────────────────────────────────────────────────

class TestRunClinicaltrialsDq:
    def test_run_clinicaltrials_dq_clean_data(self) -> None:
        records = [_ct_record(nct_id=f"NCT0500000{i}") for i in range(4)]
        results = run_clinicaltrials_dq(records)
        assert not has_blocking_failures(results)

    def test_run_clinicaltrials_dq_null_nct_id(self) -> None:
        records = [_ct_record(nct_id=None)]
        results = run_clinicaltrials_dq(records)
        assert has_blocking_failures(results)
