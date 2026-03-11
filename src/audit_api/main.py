"""Audit API — returns evidence manifests with execution timelines.

Endpoints
---------
GET  /health              — liveness probe
GET  /v1/audit/{id}       — full evidence manifest + execution timeline
"""
from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any

import redis.asyncio as aioredis
from fastapi import FastAPI, HTTPException

from src.audit_api.config import get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


@asynccontextmanager
async def _lifespan(app: FastAPI):  # type: ignore[type-arg]
    global _redis  # noqa: PLW0603
    config = get_config()
    redis_url = (
        f"redis://:{config.redis_password}@{config.redis_host}:{config.redis_port}"
        if config.redis_password
        else f"redis://{config.redis_host}:{config.redis_port}"
    )
    logger.info("Connecting to Redis at %s:%d …", config.redis_host, config.redis_port)
    _redis = aioredis.from_url(redis_url, decode_responses=True)
    logger.info("Audit API ready.")
    yield
    if _redis:
        await _redis.aclose()
    _redis = None


app = FastAPI(
    title="Biomedical AI — Audit API",
    version="5.0.0",
    lifespan=_lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": "audit-api", "phase": "5"}


@app.get("/v1/audit/{manifest_id}")
async def get_audit(manifest_id: str) -> dict[str, Any]:
    """Return the full evidence manifest and execution timeline for a query run.

    Parameters
    ----------
    manifest_id:
        UUID of the evidence manifest produced by the agent pipeline.

    Returns
    -------
    dict
        Full manifest including:
        - ``manifest_id``, ``query_id``, ``question``, ``filters``
        - ``answer`` (background, evidence, statistics, conclusion)
        - ``citations`` list
        - ``review_status``, ``review_feedback``
        - ``execution_timeline`` list of per-step records
        - ``retrieved_doc_count``, ``feature_enriched_count``, ``created_at``
    """
    if _redis is None:
        raise HTTPException(status_code=503, detail="Service not ready")

    try:
        raw = await _redis.get(f"manifest:{manifest_id}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Redis get failed for manifest_id=%s: %s", manifest_id, exc)
        raise HTTPException(status_code=503, detail="Storage unavailable") from exc

    if raw is None:
        raise HTTPException(
            status_code=404,
            detail=f"Audit record not found for manifest_id={manifest_id}. "
                   "Manifests are retained for 24 hours.",
        )

    manifest: dict[str, Any] = json.loads(raw)

    # Ensure execution_timeline key always present
    manifest.setdefault("execution_timeline", [])
    return manifest
