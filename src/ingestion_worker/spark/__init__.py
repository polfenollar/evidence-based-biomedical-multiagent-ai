"""Spark utilities: session builder, schemas, and Iceberg write jobs."""
from src.ingestion_worker.spark.session import build_spark_session
from src.ingestion_worker.spark.schemas import (
    RAW_PUBMED_SCHEMA,
    RAW_CLINICALTRIALS_SCHEMA,
    CURATED_ARTICLES_SCHEMA,
    CURATED_TRIALS_SCHEMA,
)
from src.ingestion_worker.spark.jobs import (
    write_raw_pubmed,
    write_raw_clinicaltrials,
    curate_pubmed,
    curate_clinicaltrials,
    get_snapshot_id,
)

__all__ = [
    "build_spark_session",
    "RAW_PUBMED_SCHEMA",
    "RAW_CLINICALTRIALS_SCHEMA",
    "CURATED_ARTICLES_SCHEMA",
    "CURATED_TRIALS_SCHEMA",
    "write_raw_pubmed",
    "write_raw_clinicaltrials",
    "curate_pubmed",
    "curate_clinicaltrials",
    "get_snapshot_id",
]
