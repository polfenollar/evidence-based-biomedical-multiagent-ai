"""SparkSession factory for the biomedical ingestion pipeline.

Configures:
- Apache Iceberg runtime (via Nessie REST catalog)
- Nessie Spark extensions
- AWS/S3A filesystem for MinIO
- S3A endpoint override and path-style access
"""
from __future__ import annotations

import os

from pyspark.sql import SparkSession

from src.ingestion_worker.config import IngestionConfig


# JAR coordinates resolved at runtime by Spark's package downloader
_SPARK_PACKAGES = ",".join(
    [
        "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.7.0",
        "org.projectnessie.nessie-integrations:nessie-spark-extensions-3.5_2.12:0.99.0",
        "org.apache.hadoop:hadoop-aws:3.3.4",
        "com.amazonaws:aws-java-sdk-bundle:1.12.367",
    ]
)

_SQL_EXTENSIONS = ",".join(
    [
        "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions",
        "org.projectnessie.spark.extensions.NessieSparkSessionExtensions",
    ]
)


def build_spark_session(
    config: IngestionConfig,
    app_name: str = "biomedical-ingestion",
) -> SparkSession:
    """Build and return a configured SparkSession.

    When the environment variable ``SPARK_LOCAL`` is set to ``true`` the
    session uses ``local[*]`` master, which is suitable for unit / integration
    tests without a Spark cluster.

    Parameters
    ----------
    config:
        IngestionConfig with connection details.
    app_name:
        Spark application name shown in the UI.

    Returns
    -------
    SparkSession
        Fully configured session with Iceberg + Nessie catalog.
    """
    local_mode = os.environ.get("SPARK_LOCAL", "false").lower() == "true"
    master = "local[*]" if local_mode else os.environ.get("SPARK_MASTER", "local[*]")

    # Strip trailing slash from warehouse path for Nessie config
    warehouse = config.iceberg_warehouse.rstrip("/")
    # Nessie URI without /api/v2 suffix for catalog config
    nessie_base_uri = config.nessie_uri.rstrip("/")

    builder = (
        SparkSession.builder.appName(app_name)
        .master(master)
        # ── Package downloads ──────────────────────────────────────────
        .config("spark.jars.packages", _SPARK_PACKAGES)
        # ── SQL extensions ─────────────────────────────────────────────
        .config("spark.sql.extensions", _SQL_EXTENSIONS)
        # ── Default catalog ────────────────────────────────────────────
        .config("spark.sql.defaultCatalog", "nessie")
        # ── Nessie catalog ─────────────────────────────────────────────
        .config(
            "spark.sql.catalog.nessie",
            "org.apache.iceberg.spark.SparkCatalog",
        )
        .config(
            "spark.sql.catalog.nessie.catalog-impl",
            "org.apache.iceberg.nessie.NessieCatalog",
        )
        .config("spark.sql.catalog.nessie.uri", nessie_base_uri)
        .config("spark.sql.catalog.nessie.ref", config.nessie_ref)
        .config("spark.sql.catalog.nessie.warehouse", warehouse)
        # Use HadoopFileIO which delegates to S3A (AWS SDK v1 compatible)
        .config("spark.sql.catalog.nessie.io-impl", "org.apache.iceberg.hadoop.HadoopFileIO")
        # ── S3A / MinIO ────────────────────────────────────────────────
        .config(
            "spark.hadoop.fs.s3a.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        # Alias bare s3:// scheme to S3A (Nessie stores warehouse as s3://)
        .config(
            "spark.hadoop.fs.s3.impl",
            "org.apache.hadoop.fs.s3a.S3AFileSystem",
        )
        .config("spark.hadoop.fs.s3a.endpoint", config.minio_endpoint)
        .config("spark.hadoop.fs.s3a.access.key", config.minio_access_key)
        .config("spark.hadoop.fs.s3a.secret.key", config.minio_secret_key)
        .config("spark.hadoop.fs.s3a.path.style.access", "true")
        .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
        # s3:// credentials (same as s3a since they share S3AFileSystem)
        .config("spark.hadoop.fs.s3.access.key", config.minio_access_key)
        .config("spark.hadoop.fs.s3.secret.key", config.minio_secret_key)
        .config("spark.hadoop.fs.s3.endpoint", config.minio_endpoint)
        .config("spark.hadoop.fs.s3.path.style.access", "true")
        .config("spark.hadoop.fs.s3.connection.ssl.enabled", "false")
        # ── Memory settings for local / test mode ──────────────────────
        .config("spark.driver.memory", os.environ.get("SPARK_DRIVER_MEMORY", "2g"))
        .config("spark.executor.memory", os.environ.get("SPARK_EXECUTOR_MEMORY", "2g"))
    )

    return builder.getOrCreate()
