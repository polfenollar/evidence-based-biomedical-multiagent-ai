"""Configuration for the audit-api service."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass
class AuditApiConfig:
    redis_host: str
    redis_port: int
    redis_password: str


def get_config() -> AuditApiConfig:
    return AuditApiConfig(
        redis_host=os.environ.get("REDIS_HOST", "redis"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
    )
