"""Configuration for the feature worker.

Reads from environment variables with sensible defaults for the
docker-compose stack.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class FeatureConfig:
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    redis_host: str
    redis_port: int
    redis_password: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    nessie_uri: str
    temporal_address: str
    temporal_namespace: str
    pipeline_version: str


def get_config() -> FeatureConfig:
    """Build a FeatureConfig from environment variables."""
    return FeatureConfig(
        postgres_host=os.environ.get("POSTGRES_HOST", "postgres"),
        postgres_port=int(os.environ.get("POSTGRES_PORT", "5432")),
        postgres_user=os.environ.get("POSTGRES_USER", "postgres"),
        postgres_password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        redis_host=os.environ.get("REDIS_HOST", "redis"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
        minio_endpoint=os.environ.get("MINIO_ENDPOINT", "http://minio:9000"),
        minio_access_key=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
        minio_secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
        nessie_uri=os.environ.get("NESSIE_URI", "http://nessie:19120/api/v2"),
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
    )
