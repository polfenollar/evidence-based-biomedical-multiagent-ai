"""PySpark StructType schemas for raw and curated biomedical tables.

All list-valued fields (``authors``, ``conditions``, ``interventions``,
``primary_outcomes``) are stored as JSON-serialised strings in the raw layer
for maximum schema flexibility.  The curated layer may parse them back into
``ArrayType`` columns during the curation job.
"""
from __future__ import annotations

from pyspark.sql.types import (
    ArrayType,
    IntegerType,
    StringType,
    StructField,
    StructType,
    TimestampType,
)

# ── Shared provenance fields ────────────────────────────────────────────────

_PROVENANCE_FIELDS = [
    StructField("source_name", StringType(), nullable=False),
    StructField("source_version", StringType(), nullable=True),
    StructField("source_uri", StringType(), nullable=True),
    StructField("ingested_at", StringType(), nullable=False),
    StructField("ingestion_run_id", StringType(), nullable=False),
    StructField("pipeline_version", StringType(), nullable=False),
]

# ── Raw PubMed ──────────────────────────────────────────────────────────────

RAW_PUBMED_SCHEMA = StructType(
    [
        StructField("pmid", StringType(), nullable=False),
        StructField("title", StringType(), nullable=True),
        StructField("abstract", StringType(), nullable=True),
        # Serialised as JSON array string: '["Author A", "Author B"]'
        StructField("authors", StringType(), nullable=True),
        StructField("publication_date", StringType(), nullable=True),
        StructField("journal", StringType(), nullable=True),
    ]
    + _PROVENANCE_FIELDS
)

# ── Raw ClinicalTrials ──────────────────────────────────────────────────────

RAW_CLINICALTRIALS_SCHEMA = StructType(
    [
        StructField("nct_id", StringType(), nullable=False),
        StructField("brief_title", StringType(), nullable=True),
        # Serialised as JSON array string
        StructField("conditions", StringType(), nullable=True),
        StructField("interventions", StringType(), nullable=True),
        StructField("primary_outcomes", StringType(), nullable=True),
        StructField("sample_size", IntegerType(), nullable=True),
        StructField("status", StringType(), nullable=True),
        StructField("start_date", StringType(), nullable=True),
        StructField("completion_date", StringType(), nullable=True),
    ]
    + _PROVENANCE_FIELDS
)

# ── Curated articles (PubMed) ───────────────────────────────────────────────

CURATED_ARTICLES_SCHEMA = StructType(
    [
        StructField("pmid", StringType(), nullable=False),
        StructField("title", StringType(), nullable=True),
        StructField("abstract", StringType(), nullable=True),
        StructField("authors", StringType(), nullable=True),
        StructField("publication_date", StringType(), nullable=True),
        StructField("journal", StringType(), nullable=True),
        StructField("snippet_count", IntegerType(), nullable=True),
        StructField("curated_at", StringType(), nullable=False),
    ]
    + _PROVENANCE_FIELDS
)

# ── Curated trials (ClinicalTrials) ────────────────────────────────────────

CURATED_TRIALS_SCHEMA = StructType(
    [
        StructField("nct_id", StringType(), nullable=False),
        StructField("brief_title", StringType(), nullable=True),
        StructField("conditions", StringType(), nullable=True),
        StructField("interventions", StringType(), nullable=True),
        StructField("primary_outcomes", StringType(), nullable=True),
        StructField("sample_size", IntegerType(), nullable=True),
        StructField("status", StringType(), nullable=True),
        StructField("start_date", StringType(), nullable=True),
        StructField("completion_date", StringType(), nullable=True),
        StructField("curated_at", StringType(), nullable=False),
    ]
    + _PROVENANCE_FIELDS
)
