"""FastAPI service for feature lookups from the Feast online store.

Endpoints
---------
GET  /health                       — liveness probe
GET  /v1/features/article/{pmid}   — single article feature lookup
GET  /v1/features/trial/{nct_id}   — single trial feature lookup
POST /v1/features/articles/batch   — batch article feature lookup
POST /v1/features/trials/batch     — batch trial feature lookup
"""
from __future__ import annotations

import logging
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.feature_api.config import FeatureApiConfig, get_config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_YAML_TEMPLATE = """\
project: biomedical
registry:
  registry_type: sql
  path: postgresql+psycopg2://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/feast_registry
provider: local
online_store:
  type: redis
  connection_string: "{redis_host}:{redis_port},password={redis_password}"
offline_store:
  type: file
entity_key_serialization_version: 2
"""

# Module-level store reference populated at startup
_store: Any = None


def _build_store(config: FeatureApiConfig) -> Any:
    """Build and return a :class:`feast.FeatureStore` from ``config``."""
    import feast  # noqa: F401 — ensure feast is installed

    from feast import FeatureStore

    yaml_content = _YAML_TEMPLATE.format(
        postgres_user=config.postgres_user,
        postgres_password=config.postgres_password,
        postgres_host=config.postgres_host,
        postgres_port=config.postgres_port,
        redis_host=config.redis_host,
        redis_port=config.redis_port,
        redis_password=config.redis_password,
    )

    tmpdir = tempfile.mkdtemp(prefix="feast_api_")
    yaml_path = Path(tmpdir) / "feature_store.yaml"
    yaml_path.write_text(yaml_content, encoding="utf-8")

    return FeatureStore(repo_path=tmpdir)


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    global _store
    config = get_config()
    logger.info("Building Feast FeatureStore on startup …")
    _store = _build_store(config)
    logger.info("Feast FeatureStore ready.")
    yield
    _store = None


app = FastAPI(
    title="Biomedical Feature API",
    version="0.1.0",
    lifespan=lifespan,
)


# ── Request / response models ──────────────────────────────────────────────────


class ArticleBatchRequest(BaseModel):
    pmids: list[str]


class TrialBatchRequest(BaseModel):
    nct_ids: list[str]


# ── Helpers ────────────────────────────────────────────────────────────────────


def _lookup_article_features(pmid: str) -> dict[str, Any]:
    """Look up article_stats for a single pmid from the online store.

    Parameters
    ----------
    pmid:
        The PubMed ID to look up.

    Returns
    -------
    dict
        Feature values including ``feature_view_version`` and ``snapshot_ref``.

    Raises
    ------
    HTTPException
        404 if the feature view is not found or the entity key has no data.
    """
    import pandas as pd

    try:
        feature_vector = _store.get_online_features(
            features=[
                "article_stats:title_word_count",
                "article_stats:abstract_word_count",
                "article_stats:publication_year",
                "article_stats:has_abstract",
                "article_stats:journal_encoded",
                "article_stats:snapshot_ref",
            ],
            entity_rows=[{"pmid": pmid}],
        ).to_dict()
    except Exception as exc:
        logger.warning("article feature lookup failed for pmid=%s: %s", pmid, exc)
        raise HTTPException(status_code=404, detail=f"Features not found for pmid={pmid}") from exc

    # Check if we got any data back (Feast returns None values for missing keys)
    title_wc = feature_vector.get("title_word_count", [None])
    if not title_wc or title_wc[0] is None:
        raise HTTPException(status_code=404, detail=f"Features not found for pmid={pmid}")

    snapshot_ref_val = feature_vector.get("snapshot_ref", [None])
    snapshot_ref = snapshot_ref_val[0] if snapshot_ref_val else None

    return {
        "pmid": pmid,
        "title_word_count": feature_vector.get("title_word_count", [None])[0],
        "abstract_word_count": feature_vector.get("abstract_word_count", [None])[0],
        "publication_year": feature_vector.get("publication_year", [None])[0],
        "has_abstract": feature_vector.get("has_abstract", [None])[0],
        "journal_encoded": feature_vector.get("journal_encoded", [None])[0],
        "snapshot_ref": snapshot_ref,
        "feature_view_version": "article_stats",
    }


def _lookup_trial_features(nct_id: str) -> dict[str, Any]:
    """Look up trial_stats for a single nct_id from the online store.

    Parameters
    ----------
    nct_id:
        The NCT ID to look up.

    Returns
    -------
    dict
        Feature values including ``feature_view_version`` and ``snapshot_ref``.

    Raises
    ------
    HTTPException
        404 if the feature view is not found or the entity key has no data.
    """
    try:
        feature_vector = _store.get_online_features(
            features=[
                "trial_stats:sample_size",
                "trial_stats:has_outcomes",
                "trial_stats:status_encoded",
                "trial_stats:condition_count",
                "trial_stats:snapshot_ref",
            ],
            entity_rows=[{"nct_id": nct_id}],
        ).to_dict()
    except Exception as exc:
        logger.warning("trial feature lookup failed for nct_id=%s: %s", nct_id, exc)
        raise HTTPException(status_code=404, detail=f"Features not found for nct_id={nct_id}") from exc

    sample_size_val = feature_vector.get("sample_size", [None])
    if not sample_size_val or sample_size_val[0] is None:
        raise HTTPException(status_code=404, detail=f"Features not found for nct_id={nct_id}")

    snapshot_ref_val = feature_vector.get("snapshot_ref", [None])
    snapshot_ref = snapshot_ref_val[0] if snapshot_ref_val else None

    return {
        "nct_id": nct_id,
        "sample_size": feature_vector.get("sample_size", [None])[0],
        "has_outcomes": feature_vector.get("has_outcomes", [None])[0],
        "status_encoded": feature_vector.get("status_encoded", [None])[0],
        "condition_count": feature_vector.get("condition_count", [None])[0],
        "snapshot_ref": snapshot_ref,
        "feature_view_version": "trial_stats",
    }


# ── Routes ─────────────────────────────────────────────────────────────────────


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "phase": "3"}


@app.get("/v1/features/article/{pmid}")
async def get_article_features(pmid: str) -> dict[str, Any]:
    """Look up article_stats features for a single article by PubMed ID.

    Parameters
    ----------
    pmid:
        The PubMed ID of the article.

    Returns
    -------
    dict
        Feature values for the article plus ``feature_view_version`` and
        ``snapshot_ref``.
    """
    return _lookup_article_features(pmid)


@app.get("/v1/features/trial/{nct_id}")
async def get_trial_features(nct_id: str) -> dict[str, Any]:
    """Look up trial_stats features for a single trial by NCT ID.

    Parameters
    ----------
    nct_id:
        The NCT ID of the clinical trial.

    Returns
    -------
    dict
        Feature values for the trial plus ``feature_view_version`` and
        ``snapshot_ref``.
    """
    return _lookup_trial_features(nct_id)


@app.post("/v1/features/articles/batch")
async def get_article_features_batch(
    request: ArticleBatchRequest,
) -> list[dict[str, Any]]:
    """Batch lookup of article_stats features.

    Parameters
    ----------
    request:
        Body containing ``pmids`` list.

    Returns
    -------
    list[dict]
        List of feature dicts for each pmid that was found.  Missing pmids
        are omitted from the result rather than raising a 404 for the whole
        batch.
    """
    results = []
    for pmid in request.pmids:
        try:
            results.append(_lookup_article_features(pmid))
        except HTTPException:
            logger.debug("article batch: pmid=%s not found, skipping", pmid)
    return results


@app.post("/v1/features/trials/batch")
async def get_trial_features_batch(
    request: TrialBatchRequest,
) -> list[dict[str, Any]]:
    """Batch lookup of trial_stats features.

    Parameters
    ----------
    request:
        Body containing ``nct_ids`` list.

    Returns
    -------
    list[dict]
        List of feature dicts for each nct_id that was found.  Missing
        nct_ids are omitted from the result rather than raising a 404 for
        the whole batch.
    """
    results = []
    for nct_id in request.nct_ids:
        try:
            results.append(_lookup_trial_features(nct_id))
        except HTTPException:
            logger.debug("trial batch: nct_id=%s not found, skipping", nct_id)
    return results
