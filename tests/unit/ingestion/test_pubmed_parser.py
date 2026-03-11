"""Unit tests for PubMedParser."""
from __future__ import annotations

import pytest

from src.ingestion_worker.parsers.pubmed import PubMedParser

_RUN_ID = "test-run-001"
_PIPELINE_VERSION = "0.1.0"

_VALID_RECORD = {
    "pmid": "38000001",
    "title": "Machine learning for cardiovascular risk",
    "abstract": "An abstract describing the study.",
    "authors": ["Smith JA", "Johnson KL"],
    "publication_date": "2024-03-15",
    "journal": "Diabetes Care",
    "source_version": "2024-01",
    "source_uri": "ftp://ftp.ncbi.nlm.nih.gov/sample.xml",
}


@pytest.fixture
def parser() -> PubMedParser:
    return PubMedParser()


class TestParseValidRecord:
    def test_parse_valid_record(self, parser: PubMedParser) -> None:
        result = parser.parse_record(_VALID_RECORD, _RUN_ID, _PIPELINE_VERSION)
        assert result["pmid"] == "38000001"
        assert result["title"] == "Machine learning for cardiovascular risk"
        assert result["source_name"] == "pubmed"
        assert result["publication_date"] == "2024-03-15"

    def test_provenance_fields_set(self, parser: PubMedParser) -> None:
        result = parser.parse_record(_VALID_RECORD, _RUN_ID, _PIPELINE_VERSION)
        assert result["ingested_at"]
        assert result["ingestion_run_id"] == _RUN_ID
        assert result["pipeline_version"] == _PIPELINE_VERSION
        assert result["source_name"] == "pubmed"
        assert result["source_version"] == "2024-01"
        assert result["source_uri"] == "ftp://ftp.ncbi.nlm.nih.gov/sample.xml"


class TestMissingPmid:
    def test_parse_missing_pmid(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD}
        del record["pmid"]
        with pytest.raises(ValueError, match="pmid"):
            parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)

    def test_parse_null_pmid(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "pmid": None}
        with pytest.raises(ValueError, match="pmid"):
            parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)

    def test_parse_empty_string_pmid(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "pmid": "  "}
        with pytest.raises(ValueError, match="pmid"):
            parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)


class TestDateNormalization:
    def test_normalize_date_full(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "publication_date": "2023-01-15"}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["publication_date"] == "2023-01-15"

    def test_normalize_date_year_month(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "publication_date": "2023-06"}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["publication_date"] == "2023-06"

    def test_normalize_date_year_only(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "publication_date": "2023"}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["publication_date"] == "2023"

    def test_normalize_date_invalid_returns_none(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "publication_date": "not-a-date"}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["publication_date"] is None

    def test_normalize_date_none(self, parser: PubMedParser) -> None:
        record = {**_VALID_RECORD, "publication_date": None}
        result = parser.parse_record(record, _RUN_ID, _PIPELINE_VERSION)
        assert result["publication_date"] is None


class TestParseBatch:
    def _make_records(self, count: int, start: int = 1) -> list[dict]:
        return [
            {
                **_VALID_RECORD,
                "pmid": str(38000000 + start + i),
                "title": f"Valid title {start + i}",
            }
            for i in range(count)
        ]

    def _make_invalid_records(self, count: int) -> list[dict]:
        return [
            {**_VALID_RECORD, "pmid": None, "title": f"Invalid {i}"}
            for i in range(count)
        ]

    def test_parse_batch_all_valid(self, parser: PubMedParser) -> None:
        records = self._make_records(5)
        parsed, rejected = parser.parse_batch(records, _RUN_ID, _PIPELINE_VERSION)
        assert len(parsed) == 5
        assert len(rejected) == 0

    def test_parse_batch_mixed(self, parser: PubMedParser) -> None:
        valid = self._make_records(10)
        invalid = self._make_invalid_records(2)
        records = valid + invalid
        parsed, rejected = parser.parse_batch(records, _RUN_ID, _PIPELINE_VERSION)
        assert len(parsed) == 10
        assert len(rejected) == 2

    def test_rejected_records_have_parse_error(self, parser: PubMedParser) -> None:
        records = self._make_invalid_records(1)
        _, rejected = parser.parse_batch(records, _RUN_ID, _PIPELINE_VERSION)
        assert len(rejected) == 1
        assert "parse_error" in rejected[0]
        assert rejected[0]["parse_error"]

    def test_parse_batch_empty(self, parser: PubMedParser) -> None:
        parsed, rejected = parser.parse_batch([], _RUN_ID, _PIPELINE_VERSION)
        assert parsed == []
        assert rejected == []
