"""Integration test fixtures.

These fixtures require the docker-compose stack to be running.
Run integration tests with: pytest -m integration
Skip with: pytest -m "not integration"
"""
from __future__ import annotations

import os

import pytest

from src.ingestion_worker.config import IngestionConfig, get_config


@pytest.fixture(scope="session")
def ingestion_config() -> IngestionConfig:
    """Build IngestionConfig from environment variables.

    Overrides minio_endpoint and nessie_uri to use localhost when running
    tests from the host machine against the docker-compose stack.
    """
    config = get_config()
    # When running tests from the host, services are reachable on localhost
    if os.environ.get("SPARK_LOCAL", "false").lower() == "true":
        config = IngestionConfig(
            minio_endpoint=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
            minio_access_key=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
            minio_secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
            nessie_uri=os.environ.get("NESSIE_URI", "http://localhost:19120/api/v2"),
            nessie_ref=os.environ.get("NESSIE_REF", "main"),
            iceberg_warehouse=os.environ.get(
                "ICEBERG_WAREHOUSE", "s3://iceberg-warehouse/"
            ),
            temporal_address=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
            temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
            pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
            ingestion_run_id=os.environ.get(
                "INGESTION_RUN_ID", "integration-test-run"
            ),
        )
    return config


@pytest.fixture(scope="session")
def spark_session(ingestion_config: IngestionConfig):
    """Build a SparkSession for integration tests.

    Uses SPARK_LOCAL=true for local master mode.
    """
    os.environ.setdefault("SPARK_LOCAL", "true")
    from src.ingestion_worker.spark.session import build_spark_session

    spark = build_spark_session(ingestion_config, app_name="biomedical-integration-tests")
    yield spark
    spark.stop()
