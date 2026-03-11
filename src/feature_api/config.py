"""Configuration for the feature API service.

Reads from environment variables with sensible defaults for the
docker-compose stack.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class FeatureApiConfig:
    postgres_host: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    redis_host: str
    redis_port: int
    redis_password: str


def get_config() -> FeatureApiConfig:
    """Build a FeatureApiConfig from environment variables."""
    return FeatureApiConfig(
        postgres_host=os.environ.get("POSTGRES_HOST", "postgres"),
        postgres_port=int(os.environ.get("POSTGRES_PORT", "5432")),
        postgres_user=os.environ.get("POSTGRES_USER", "postgres"),
        postgres_password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        redis_host=os.environ.get("REDIS_HOST", "redis"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
    )
