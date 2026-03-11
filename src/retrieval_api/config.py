"""Configuration for the retrieval API.

Reads from environment variables with sensible defaults for the
docker-compose stack.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class RetrievalConfig:
    qdrant_url: str


def get_config() -> RetrievalConfig:
    """Build a RetrievalConfig from environment variables."""
    return RetrievalConfig(
        qdrant_url=os.environ.get("QDRANT_URL", "http://qdrant:6333"),
    )
