"""Configuration for the embedding worker.

Reads from environment variables with sensible defaults for the
docker-compose stack.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class EmbeddingConfig:
    qdrant_url: str
    nessie_uri: str
    temporal_address: str
    temporal_namespace: str
    embedding_model: str
    embedding_model_version: str
    batch_size: int
    pipeline_version: str


def get_config() -> EmbeddingConfig:
    """Build an EmbeddingConfig from environment variables."""
    return EmbeddingConfig(
        qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
        nessie_uri=os.environ.get("NESSIE_URI", "http://nessie:19120/api/v2"),
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        embedding_model=os.environ.get("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
        embedding_model_version=os.environ.get("EMBEDDING_MODEL_VERSION", "1"),
        batch_size=int(os.environ.get("EMBEDDING_BATCH_SIZE", "32")),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
    )
