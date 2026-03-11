"""Integration tests for Spark + Iceberg + Nessie stack.

These tests require the docker-compose infrastructure to be running.
Run with: pytest -m integration
Skip with: pytest -m "not integration"
"""
from __future__ import annotations

import os

import pytest
from pyspark.sql import SparkSession

from src.ingestion_worker.config import IngestionConfig
from src.ingestion_worker.parsers.pubmed import PubMedParser
from src.ingestion_worker.spark.jobs import (
    curate_pubmed,
    write_raw_pubmed,
    get_snapshot_id,
)

pytestmark = pytest.mark.integration

_RUN_ID = "integration-test-run"
_PIPELINE_VERSION = "0.1.0"

_SAMPLE_RECORDS = [
    {
        "pmid": "99000001",
        "title": "Integration test article A",
        "abstract": "Abstract A",
        "authors": ["Author A"],
        "publication_date": "2024-01-01",
        "journal": "Test Journal",
        "source_version": "2024-01",
        "source_uri": "ftp://ftp.ncbi.nlm.nih.gov/integration-test.xml",
    },
    {
        "pmid": "99000002",
        "title": "Integration test article B",
        "abstract": "Abstract B",
        "authors": ["Author B"],
        "publication_date": "2024-02-01",
        "journal": "Test Journal",
        "source_version": "2024-01",
        "source_uri": "ftp://ftp.ncbi.nlm.nih.gov/integration-test.xml",
    },
]


@pytest.fixture(scope="module")
def parsed_records() -> list[dict]:
    parser = PubMedParser()
    parsed, _ = parser.parse_batch(_SAMPLE_RECORDS, _RUN_ID, _PIPELINE_VERSION)
    return parsed


@pytest.mark.integration
def test_spark_can_create_namespace(spark_session: SparkSession) -> None:
    """CREATE NAMESPACE IF NOT EXISTS must succeed without exception."""
    spark_session.sql("CREATE NAMESPACE IF NOT EXISTS nessie.biomedical")
    namespaces = [
        row[0]
        for row in spark_session.sql("SHOW NAMESPACES IN nessie").collect()
    ]
    assert any("biomedical" in ns for ns in namespaces)


@pytest.mark.integration
def test_write_raw_pubmed_returns_snapshot_id(
    spark_session: SparkSession,
    ingestion_config: IngestionConfig,
    parsed_records: list[dict],
) -> None:
    """Writing raw PubMed records must return a non-empty snapshot ID."""
    snapshot_id = write_raw_pubmed(spark_session, parsed_records, ingestion_config)
    assert isinstance(snapshot_id, str)
    assert snapshot_id  # non-empty


@pytest.mark.integration
def test_write_curated_articles_deduplication(
    spark_session: SparkSession,
    ingestion_config: IngestionConfig,
    parsed_records: list[dict],
) -> None:
    """Writing the same records twice must not produce duplicates in curated table."""
    # Write twice
    write_raw_pubmed(spark_session, parsed_records, ingestion_config)
    write_raw_pubmed(spark_session, parsed_records, ingestion_config)

    curate_pubmed(spark_session, ingestion_config)

    curated_df = spark_session.table("nessie.biomedical.curated_articles")
    pmids = [row["pmid"] for row in curated_df.select("pmid").collect()]

    # pmids must be unique in the curated layer
    assert len(pmids) == len(set(pmids)), (
        f"Duplicates found in curated_articles: {pmids}"
    )


@pytest.mark.integration
def test_snapshot_id_queryable(
    spark_session: SparkSession,
    ingestion_config: IngestionConfig,
    parsed_records: list[dict],
) -> None:
    """Snapshot ID returned by get_snapshot_id must be a valid integer string."""
    write_raw_pubmed(spark_session, parsed_records, ingestion_config)
    snapshot_id = get_snapshot_id(
        spark_session, "nessie.biomedical.raw_pubmed_articles"
    )
    assert snapshot_id not in ("unknown", "")
    # Iceberg snapshot IDs are signed 64-bit integers
    try:
        int(snapshot_id)
    except ValueError:
        pytest.fail(f"snapshot_id is not a valid integer string: {snapshot_id!r}")
