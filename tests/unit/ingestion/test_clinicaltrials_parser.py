"""Unit tests for ClinicalTrialsParser."""
from __future__ import annotations

import pytest

from src.ingestion_worker.parsers.clinicaltrials import ClinicalTrialsParser

_RUN_ID = "test-run-001"
_PIPELINE_VERSION = "0.1.0"

_VALID_RECORD = {
    "nct_id": "NCT05000001",
    "brief_title": "CRISPR Gene Editing for Sickle Cell Disease",
    "conditions": ["Sickle Cell Disease"],
    "interventions": ["CTX001 gene therapy"],
    "primary_outcomes": ["Transfusion independence at 12 months"],
    "sample_size": 45,
    "status": "RECRUITING",
    "start_date": "2023-06-01",
    "completion_date": "2026-12-31",
    "source_version": "2024-01",
    "source_uri": "https://clinicaltrials.gov/sample.zip",
}


@pytest.fixture
def parser() -> ClinicalTrialsParser:
    return ClinicalTrialsParser()


class TestParseValidRecord:
    def test_parse_valid_record(self, parser: ClinicalTrialsParser) -> None:
        result = parser.parse_record(_VALID_RECORD, _RUN_ID, _PIPELINE_VERSION)
        assert result["nct_id"] == "NCT05000001"
        assert result["brief_title"] == "CRISPR Gene Editing for Sickle Cell Disease"
        assert result["source_name"] == "clinicaltrials"
        assert result["status"] == "RECRUITING"
        assert result["sample_size"] == 45

    def test_provenance_fields_set(self, parser: ClinicalTrialsParser) -> None:
        result = parser.parse_record(_VALID_RECORD, _RUN_ID, _PIPELINE_VERSION)
        assert result["ingested_at"]
        assert result["ingestion_run_id"] == _RUN_ID
        assert result["pipeline_version"] == _PIPELINE_VERSION
        assert result["source_name"] == "clinicaltrials"
        assert result["source_version"] == "2024-01"
        assert result["source_uri"] == "https://clinicaltrials.gov/sample.zip"

    def test_sample_size_none_allowed(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD, "sample_size": None}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["sample_size"] is None

    def test_completion_date_none_allowed(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD, "completion_date": None}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["completion_date"] is None


class TestMissingNctId:
    def test_parse_missing_nct_id(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD}
        del record["nct_id"]
        with pytest.raises(ValueError, match="nct_id"):
            parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)

    def test_parse_null_nct_id(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD, "nct_id": None}
        with pytest.raises(ValueError, match="nct_id"):
            parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)

    def test_parse_empty_string_nct_id(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD, "nct_id": ""}
        with pytest.raises(ValueError, match="nct_id"):
            parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)


class TestDateNormalization:
    def test_start_date_full(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD, "start_date": "2023-06-01"}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["start_date"] == "2023-06-01"

    def test_start_date_invalid_returns_none(self, parser: ClinicalTrialsParser) -> None:
        record = {**_VALID_RECORD, "start_date": "invalid-date"}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["start_date"] is None


class TestParseBatch:
    def _make_records(self, count: int, start: int = 1) -> list[dict]:
        return [
            {
                **_VALID_RECORD,
                "nct_id": f"NCT0500{start + i:04d}",
                "brief_title": f"Valid study {start + i}",
            }
            for i in range(count)
        ]

    def _make_invalid_records(self, count: int) -> list[dict]:
        return [
            {**_VALID_RECORD, "nct_id": None, "brief_title": f"Invalid {i}"}
            for i in range(count)
        ]

    def test_parse_batch_all_valid(self, parser: ClinicalTrialsParser) -> None:
        records = self._make_records(4)
        parsed, rejected = parser.parse_batch(records, _RUN_ID, _PIPELINE_VERSION)
        assert len(parsed) == 4
        assert len(rejected) == 0

    def test_parse_batch_mixed(self, parser: ClinicalTrialsParser) -> None:
        valid = self._make_records(4)
        invalid = self._make_invalid_records(1)
        records = valid + invalid
        parsed, rejected = parser.parse_batch(records, _RUN_ID, _PIPELINE_VERSION)
        assert len(parsed) == 4
        assert len(rejected) == 1

    def test_rejected_records_have_parse_error(self, parser: ClinicalTrialsParser) -> None:
        records = self._make_invalid_records(1)
        _, rejected = parser.parse_batch(records, _RUN_ID, _PIPELINE_VERSION)
        assert "parse_error" in rejected[0]

    def test_parse_batch_empty(self, parser: ClinicalTrialsParser) -> None:
        parsed, rejected = parser.parse_batch([], _RUN_ID, _PIPELINE_VERSION)
        assert parsed == []
        assert rejected == []
