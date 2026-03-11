"""Configuration for the agent worker service."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentWorkerConfig:
    retrieval_api_url: str
    feature_api_url: str
    temporal_address: str
    temporal_namespace: str
    pipeline_version: str


def get_config() -> AgentWorkerConfig:
    """Build an AgentWorkerConfig from environment variables."""
    return AgentWorkerConfig(
        retrieval_api_url=os.environ.get("RETRIEVAL_API_URL", "http://retrieval-api:8001"),
        feature_api_url=os.environ.get("FEATURE_API_URL", "http://feature-api:8002"),
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.4.0"),
    )
