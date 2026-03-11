"""Configuration for the ingestion worker.

Reads from environment variables with sensible defaults for the
docker-compose stack.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass, field


@dataclass
class IngestionConfig:
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    nessie_uri: str
    nessie_ref: str
    iceberg_warehouse: str
    temporal_address: str
    temporal_namespace: str
    pipeline_version: str
    ingestion_run_id: str


def get_config() -> IngestionConfig:
    """Build an IngestionConfig from environment variables."""
    return IngestionConfig(
        minio_endpoint=os.environ.get("MINIO_ENDPOINT", "http://minio:9000"),
        minio_access_key=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
        minio_secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
        nessie_uri=os.environ.get("NESSIE_URI", "http://nessie:19120/api/v2"),
        nessie_ref=os.environ.get("NESSIE_REF", "main"),
        iceberg_warehouse=os.environ.get(
            "ICEBERG_WAREHOUSE", "s3://iceberg-warehouse/"
        ),
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
        ingestion_run_id=os.environ.get(
            "INGESTION_RUN_ID", str(uuid.uuid4())
        ),
    )
