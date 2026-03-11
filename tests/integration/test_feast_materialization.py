"""Integration tests for Feast feature store materialization.

Requires running infrastructure:
- PostgreSQL with ``feast_registry`` database
- Redis online store

Set ``FEAST_LOCAL=true`` and the standard connection env vars to use
localhost endpoints.

Run with: pytest -m integration tests/integration/test_feast_materialization.py
"""
from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import pytest

pytestmark = pytest.mark.integration


def _make_feature_config() -> "FeatureConfig":  # noqa: F821
    """Build a FeatureConfig suitable for localhost integration testing."""
    from src.feature_worker.config import FeatureConfig

    feast_local = os.environ.get("FEAST_LOCAL", "false").lower() == "true"

    return FeatureConfig(
        postgres_host=os.environ.get("POSTGRES_HOST", "localhost" if feast_local else "postgres"),
        postgres_port=int(os.environ.get("POSTGRES_PORT", "5432")),
        postgres_user=os.environ.get("POSTGRES_USER", "postgres"),
        postgres_password=os.environ.get("POSTGRES_PASSWORD", "postgres"),
        redis_host=os.environ.get("REDIS_HOST", "localhost" if feast_local else "redis"),
        redis_port=int(os.environ.get("REDIS_PORT", "6379")),
        redis_password=os.environ.get("REDIS_PASSWORD", ""),
        minio_endpoint=os.environ.get("MINIO_ENDPOINT", "http://localhost:9000"),
        minio_access_key=os.environ.get("MINIO_ROOT_USER", "minioadmin"),
        minio_secret_key=os.environ.get("MINIO_ROOT_PASSWORD", "minioadmin"),
        nessie_uri=os.environ.get("NESSIE_URI", "http://localhost:19120/api/v2"),
        temporal_address=os.environ.get("TEMPORAL_ADDRESS", "localhost:7233"),
        temporal_namespace=os.environ.get("TEMPORAL_NAMESPACE", "default"),
        pipeline_version=os.environ.get("PIPELINE_VERSION", "0.1.0"),
    )


def _write_article_parquet(tmpdir: str, snapshot_ref: str = "snap-test") -> str:
    """Write a sample article features parquet file and return its path."""
    now_utc = pd.Timestamp.now(tz="UTC")
    data = [
        {
            "pmid": "38000001",
            "title_word_count": 6,
            "abstract_word_count": 7,
            "publication_year": 2024,
            "has_abstract": 1,
            "journal_encoded": "Diabetes Care",
            "snapshot_ref": snapshot_ref,
            "event_timestamp": now_utc,
        },
        {
            "pmid": "38000002",
            "title_word_count": 4,
            "abstract_word_count": 0,
            "publication_year": 2023,
            "has_abstract": 0,
            "journal_encoded": "Nature Medicine",
            "snapshot_ref": snapshot_ref,
            "event_timestamp": now_utc,
        },
        {
            "pmid": "38000003",
            "title_word_count": 8,
            "abstract_word_count": 12,
            "publication_year": 2022,
            "has_abstract": 1,
            "journal_encoded": "NEJM",
            "snapshot_ref": snapshot_ref,
            "event_timestamp": now_utc,
        },
    ]
    df = pd.DataFrame(data)
    path = str(Path(tmpdir) / "article_stats.parquet")
    df.to_parquet(path, index=False)
    return path


def _write_trial_parquet(tmpdir: str, snapshot_ref: str = "snap-test") -> str:
    """Write a sample trial features parquet file and return its path."""
    now_utc = pd.Timestamp.now(tz="UTC")
    data = [
        {
            "nct_id": "NCT00000001",
            "sample_size": 250,
            "has_outcomes": 1,
            "status_encoded": "Completed",
            "condition_count": 3,
            "snapshot_ref": snapshot_ref,
            "event_timestamp": now_utc,
        },
        {
            "nct_id": "NCT00000002",
            "sample_size": 0,
            "has_outcomes": 0,
            "status_encoded": "Recruiting",
            "condition_count": 1,
            "snapshot_ref": snapshot_ref,
            "event_timestamp": now_utc,
        },
        {
            "nct_id": "NCT00000003",
            "sample_size": 500,
            "has_outcomes": 1,
            "status_encoded": "Active",
            "condition_count": 2,
            "snapshot_ref": snapshot_ref,
            "event_timestamp": now_utc,
        },
    ]
    df = pd.DataFrame(data)
    path = str(Path(tmpdir) / "trial_stats.parquet")
    df.to_parquet(path, index=False)
    return path


class TestFeatureStoreCanApply:
    def test_feature_store_can_apply(self) -> None:
        """Build a FeatureStore and apply entities + feature views without error."""
        from src.feature_worker.feast_repo.store import (
            build_feature_store,
            get_entity_definitions,
            get_feature_views,
        )

        config = _make_feature_config()
        store = build_feature_store(config)

        tmpdir = tempfile.mkdtemp(prefix="feast_test_")
        article_parquet = _write_article_parquet(tmpdir)
        trial_parquet = _write_trial_parquet(tmpdir)

        entities = get_entity_definitions()
        feature_views = get_feature_views(
            article_parquet_path=article_parquet,
            trial_parquet_path=trial_parquet,
        )

        # apply() should complete without raising
        store.apply(entities + feature_views)


class TestArticleFeaturesMaterialization:
    def test_article_features_materialization(self) -> None:
        """Materialize article features and verify online store lookup."""
        from src.feature_worker.feast_repo.store import (
            build_feature_store,
            get_entity_definitions,
            get_feature_views,
        )

        config = _make_feature_config()
        store = build_feature_store(config)

        tmpdir = tempfile.mkdtemp(prefix="feast_article_test_")
        article_parquet = _write_article_parquet(tmpdir)
        trial_parquet = _write_trial_parquet(tmpdir)

        entities = get_entity_definitions()
        feature_views = get_feature_views(
            article_parquet_path=article_parquet,
            trial_parquet_path=trial_parquet,
        )

        store.apply(entities + feature_views)

        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(hours=1)
        store.materialize(start_date=start_date, end_date=end_date)

        # Lookup a known entity
        result = store.get_online_features(
            features=[
                "article_stats:title_word_count",
                "article_stats:publication_year",
                "article_stats:has_abstract",
            ],
            entity_rows=[{"pmid": "38000001"}],
        ).to_dict()

        assert result["title_word_count"][0] == 6
        assert result["publication_year"][0] == 2024
        assert result["has_abstract"][0] == 1


class TestTrialFeaturesMaterialization:
    def test_trial_features_materialization(self) -> None:
        """Materialize trial features and verify online store lookup."""
        from src.feature_worker.feast_repo.store import (
            build_feature_store,
            get_entity_definitions,
            get_feature_views,
        )

        config = _make_feature_config()
        store = build_feature_store(config)

        tmpdir = tempfile.mkdtemp(prefix="feast_trial_test_")
        article_parquet = _write_article_parquet(tmpdir)
        trial_parquet = _write_trial_parquet(tmpdir)

        entities = get_entity_definitions()
        feature_views = get_feature_views(
            article_parquet_path=article_parquet,
            trial_parquet_path=trial_parquet,
        )

        store.apply(entities + feature_views)

        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(hours=1)
        store.materialize(start_date=start_date, end_date=end_date)

        result = store.get_online_features(
            features=[
                "trial_stats:sample_size",
                "trial_stats:has_outcomes",
                "trial_stats:condition_count",
                "trial_stats:status_encoded",
            ],
            entity_rows=[{"nct_id": "NCT00000001"}],
        ).to_dict()

        assert result["sample_size"][0] == 250
        assert result["has_outcomes"][0] == 1
        assert result["condition_count"][0] == 3
        assert result["status_encoded"][0] == "Completed"


class TestFeatureHasSnapshotRef:
    def test_feature_has_snapshot_ref(self) -> None:
        """Verify that snapshot_ref is present in materialized article features."""
        from src.feature_worker.feast_repo.store import (
            build_feature_store,
            get_entity_definitions,
            get_feature_views,
        )

        config = _make_feature_config()
        store = build_feature_store(config)

        snapshot_ref = "snap-integration-test-001"
        tmpdir = tempfile.mkdtemp(prefix="feast_snap_test_")
        article_parquet = _write_article_parquet(tmpdir, snapshot_ref=snapshot_ref)
        trial_parquet = _write_trial_parquet(tmpdir, snapshot_ref=snapshot_ref)

        entities = get_entity_definitions()
        feature_views = get_feature_views(
            article_parquet_path=article_parquet,
            trial_parquet_path=trial_parquet,
        )

        store.apply(entities + feature_views)

        end_date = datetime.now(tz=timezone.utc)
        start_date = end_date - timedelta(hours=1)
        store.materialize(start_date=start_date, end_date=end_date)

        result = store.get_online_features(
            features=["article_stats:snapshot_ref"],
            entity_rows=[{"pmid": "38000001"}],
        ).to_dict()

        assert result["snapshot_ref"][0] == snapshot_ref
