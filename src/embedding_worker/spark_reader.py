"""Spark-based readers for curated Iceberg tables.

These functions read from the ``nessie.biomedical.curated_articles`` and
``nessie.biomedical.curated_trials`` tables and return plain Python lists of
dicts so that the rest of the embedding worker has no Spark dependency.
"""
from __future__ import annotations

from typing import Any


def read_curated_articles(spark: Any) -> list[dict[str, Any]]:
    """Read all rows from ``nessie.biomedical.curated_articles``.

    Parameters
    ----------
    spark:
        Active :class:`pyspark.sql.SparkSession`.

    Returns
    -------
    list[dict]
        Each dict corresponds to one row with the curated_articles schema.
    """
    df = spark.sql("SELECT * FROM nessie.biomedical.curated_articles")
    return [row.asDict() for row in df.collect()]


def read_curated_trials(spark: Any) -> list[dict[str, Any]]:
    """Read all rows from ``nessie.biomedical.curated_trials``.

    Parameters
    ----------
    spark:
        Active :class:`pyspark.sql.SparkSession`.

    Returns
    -------
    list[dict]
        Each dict corresponds to one row with the curated_trials schema.
    """
    df = spark.sql("SELECT * FROM nessie.biomedical.curated_trials")
    return [row.asDict() for row in df.collect()]


def get_snapshot_id(spark: Any, table: str) -> str:
    """Return the current snapshot ID for an Iceberg table as a string.

    Parameters
    ----------
    spark:
        Active :class:`pyspark.sql.SparkSession`.
    table:
        Fully-qualified table name, e.g. ``nessie.biomedical.curated_articles``.

    Returns
    -------
    str
        The snapshot ID, or ``"unknown"`` if unavailable.
    """
    try:
        row = (
            spark.sql(f"SELECT snapshot_id FROM {table}.snapshots ORDER BY committed_at DESC LIMIT 1")
            .collect()
        )
        if row:
            snapshot_id = row[0]["snapshot_id"]
            return str(snapshot_id) if snapshot_id is not None else "unknown"
    except Exception:  # noqa: BLE001
        pass
    return "unknown"
