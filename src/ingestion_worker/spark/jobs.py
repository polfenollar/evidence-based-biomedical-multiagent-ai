"""Spark/Iceberg write and curation jobs.

All jobs accept a SparkSession and an IngestionConfig and return the
Iceberg snapshot ID (as a string) of the table they wrote to.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql import functions as F
from pyspark.sql.types import IntegerType

from src.ingestion_worker.config import IngestionConfig
from src.ingestion_worker.spark.schemas import (
    RAW_PUBMED_SCHEMA,
    RAW_CLINICALTRIALS_SCHEMA,
    CURATED_ARTICLES_SCHEMA,
    CURATED_TRIALS_SCHEMA,
)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _records_to_df(
    spark: SparkSession,
    records: list[dict[str, Any]],
    schema,
) -> DataFrame:
    """Convert a list of parsed dicts to a Spark DataFrame.

    List-valued fields are JSON-serialised to strings so they match the raw
    schema which stores arrays as JSON strings.
    """
    rows: list[dict[str, Any]] = []
    for rec in records:
        row: dict[str, Any] = {}
        for field in schema.fields:
            value = rec.get(field.name)
            if isinstance(value, list):
                row[field.name] = json.dumps(value)
            elif field.dataType == IntegerType() and value is not None:
                try:
                    row[field.name] = int(value)
                except (ValueError, TypeError):
                    row[field.name] = None
            else:
                row[field.name] = value
        rows.append(row)
    return spark.createDataFrame(rows, schema=schema)


def _ensure_namespace(spark: SparkSession) -> None:
    """Create the biomedical namespace if it does not already exist."""
    spark.sql("CREATE NAMESPACE IF NOT EXISTS nessie.biomedical")


def get_snapshot_id(spark: SparkSession, table_name: str) -> str:
    """Return the current snapshot ID for *table_name* as a string.

    Parameters
    ----------
    spark:
        Active SparkSession.
    table_name:
        Fully qualified table name, e.g. ``nessie.biomedical.raw_pubmed_articles``.

    Returns
    -------
    str
        Snapshot ID or ``"unknown"`` if no snapshot exists yet.
    """
    try:
        history = spark.sql(f"SELECT snapshot_id FROM {table_name}.history ORDER BY made_current_at DESC LIMIT 1")
        rows = history.collect()
        if rows:
            return str(rows[0]["snapshot_id"])
    except Exception:
        pass
    return "unknown"


# ── Raw write jobs ───────────────────────────────────────────────────────────

def write_raw_pubmed(
    spark: SparkSession,
    records: list[dict[str, Any]],
    config: IngestionConfig,
) -> str:
    """Write parsed PubMed records to the ``raw_pubmed_articles`` Iceberg table.

    The table is created with ``IF NOT EXISTS`` before writing.

    Returns
    -------
    str
        Snapshot ID after the write.
    """
    _ensure_namespace(spark)

    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS nessie.biomedical.raw_pubmed_articles (
            pmid             STRING NOT NULL,
            title            STRING,
            abstract         STRING,
            authors          STRING,
            publication_date STRING,
            journal          STRING,
            source_name      STRING NOT NULL,
            source_version   STRING,
            source_uri       STRING,
            ingested_at      STRING NOT NULL,
            ingestion_run_id STRING NOT NULL,
            pipeline_version STRING NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingestion_run_id)
        """
    )

    df = _records_to_df(spark, records, RAW_PUBMED_SCHEMA)
    df.writeTo("nessie.biomedical.raw_pubmed_articles").append()

    return get_snapshot_id(spark, "nessie.biomedical.raw_pubmed_articles")


def write_raw_clinicaltrials(
    spark: SparkSession,
    records: list[dict[str, Any]],
    config: IngestionConfig,
) -> str:
    """Write parsed ClinicalTrials records to ``raw_clinicaltrials_studies``.

    Returns
    -------
    str
        Snapshot ID after the write.
    """
    _ensure_namespace(spark)

    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS nessie.biomedical.raw_clinicaltrials_studies (
            nct_id            STRING NOT NULL,
            brief_title       STRING,
            conditions        STRING,
            interventions     STRING,
            primary_outcomes  STRING,
            sample_size       INT,
            status            STRING,
            start_date        STRING,
            completion_date   STRING,
            source_name       STRING NOT NULL,
            source_version    STRING,
            source_uri        STRING,
            ingested_at       STRING NOT NULL,
            ingestion_run_id  STRING NOT NULL,
            pipeline_version  STRING NOT NULL
        )
        USING iceberg
        PARTITIONED BY (ingestion_run_id)
        """
    )

    df = _records_to_df(spark, records, RAW_CLINICALTRIALS_SCHEMA)
    df.writeTo("nessie.biomedical.raw_clinicaltrials_studies").append()

    return get_snapshot_id(spark, "nessie.biomedical.raw_clinicaltrials_studies")


# ── Curation jobs ────────────────────────────────────────────────────────────

def curate_pubmed(
    spark: SparkSession,
    config: IngestionConfig,
) -> str:
    """Read ``raw_pubmed_articles``, deduplicate by pmid, write ``curated_articles``.

    Deduplication keeps the most-recently ingested record per ``pmid``.

    Returns
    -------
    str
        Snapshot ID after the write.
    """
    _ensure_namespace(spark)

    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS nessie.biomedical.curated_articles (
            pmid             STRING NOT NULL,
            title            STRING,
            abstract         STRING,
            authors          STRING,
            publication_date STRING,
            journal          STRING,
            snippet_count    INT,
            curated_at       STRING NOT NULL,
            source_name      STRING NOT NULL,
            source_version   STRING,
            source_uri       STRING,
            ingested_at      STRING NOT NULL,
            ingestion_run_id STRING NOT NULL,
            pipeline_version STRING NOT NULL
        )
        USING iceberg
        """
    )

    curated_at = datetime.now(timezone.utc).isoformat()

    raw_df = spark.table("nessie.biomedical.raw_pubmed_articles")

    # Deduplicate: keep the row with the latest ingested_at per pmid
    window_spec = (
        F.row_number()
        .over(
            __import__("pyspark.sql.window", fromlist=["Window"])
            .Window.partitionBy("pmid")
            .orderBy(F.col("ingested_at").desc())
        )
    )
    deduped_df = (
        raw_df.withColumn("_rn", window_spec)
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("curated_at", F.lit(curated_at))
        .withColumn("snippet_count", F.lit(0).cast(IntegerType()))
    )

    # Select only curated schema columns in order
    curated_cols = [f.name for f in CURATED_ARTICLES_SCHEMA.fields]
    deduped_df = deduped_df.select(*curated_cols)

    deduped_df.writeTo("nessie.biomedical.curated_articles").overwritePartitions()

    return get_snapshot_id(spark, "nessie.biomedical.curated_articles")


def curate_clinicaltrials(
    spark: SparkSession,
    config: IngestionConfig,
) -> str:
    """Read ``raw_clinicaltrials_studies``, deduplicate by nct_id, write ``curated_trials``.

    Returns
    -------
    str
        Snapshot ID after the write.
    """
    _ensure_namespace(spark)

    spark.sql(
        """
        CREATE TABLE IF NOT EXISTS nessie.biomedical.curated_trials (
            nct_id            STRING NOT NULL,
            brief_title       STRING,
            conditions        STRING,
            interventions     STRING,
            primary_outcomes  STRING,
            sample_size       INT,
            status            STRING,
            start_date        STRING,
            completion_date   STRING,
            curated_at        STRING NOT NULL,
            source_name       STRING NOT NULL,
            source_version    STRING,
            source_uri        STRING,
            ingested_at       STRING NOT NULL,
            ingestion_run_id  STRING NOT NULL,
            pipeline_version  STRING NOT NULL
        )
        USING iceberg
        """
    )

    curated_at = datetime.now(timezone.utc).isoformat()

    from pyspark.sql.window import Window

    raw_df = spark.table("nessie.biomedical.raw_clinicaltrials_studies")

    window_spec = (
        F.row_number()
        .over(
            Window.partitionBy("nct_id").orderBy(F.col("ingested_at").desc())
        )
    )
    deduped_df = (
        raw_df.withColumn("_rn", window_spec)
        .filter(F.col("_rn") == 1)
        .drop("_rn")
        .withColumn("curated_at", F.lit(curated_at))
    )

    curated_cols = [f.name for f in CURATED_TRIALS_SCHEMA.fields]
    deduped_df = deduped_df.select(*curated_cols)

    deduped_df.writeTo("nessie.biomedical.curated_trials").overwritePartitions()

    return get_snapshot_id(spark, "nessie.biomedical.curated_trials")
