"""Configuration for the agent-api service."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AgentApiConfig:
    temporal_address: str
    temporal_namespace: str
    retrieval_api_url: str
    feature_api_url: str
    redis_host: str
    redis_port: int
    redis_password: str


def get_config() -> AgentApiConfig:
    return AgentApiConfig(
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "temporal:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        retrieval_api_url=os.environ.get("RETRIEVAL_API_URL", "http://retrieval-api:8001"),
        feature_api_url=os.environ.get("FEATURE_API_URL", "http://feature-api:8002"),
        redis_host=os.environ.get("REDIS_HOST", "redis"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
    )
