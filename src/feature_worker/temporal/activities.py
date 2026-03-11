"""Temporal activities for the biomedical feature refresh pipeline."""
from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from temporalio import activity

from src.feature_worker.config import get_config
from src.feature_worker.features.entity_stats import (
    compute_article_stats_batch,
    compute_trial_stats_batch,
)


@dataclass
class FeatureRefreshInput:
    run_id: str
    pipeline_version: str


@dataclass
class FeatureRefreshOutput:
    run_id: str
    articles_computed: int
    trials_computed: int
    iceberg_snapshot_ref: str
    feature_view_version: str


@activity.defn
async def compute_and_materialize_activity(
    input: FeatureRefreshInput,
) -> FeatureRefreshOutput:
    """Compute features from Iceberg and materialize them to the online store.

    Steps
    -----
    1. Build a Spark session using the ingestion worker's session factory.
    2. Read ``curated_articles`` and ``curated_trials`` from Iceberg.
    3. Obtain the latest Iceberg snapshot ID for provenance tracking.
    4. Compute article and trial statistics via pure-Python batch functions.
    5. Write computed features to local parquet files.
    6. Build the Feast FeatureStore, apply definitions, and materialize.
    7. Return a :class:`FeatureRefreshOutput` summary.

    Parameters
    ----------
    input:
        :class:`FeatureRefreshInput` carrying the run_id and pipeline version.

    Returns
    -------
    FeatureRefreshOutput
    """
    # Import Spark/Feast dependencies here to avoid import overhead in
    # environments where they are not installed (e.g., unit tests).
    from src.ingestion_worker.spark.session import build_spark_session
    from src.ingestion_worker.config import IngestionConfig
    from src.feature_worker.feast_repo.store import (
        build_feature_store,
        get_entity_definitions,
        get_feature_views,
    )

    logger = activity.logger
    config = get_config()

    logger.info(
        "compute_and_materialize_activity: run_id=%s pipeline_version=%s",
        input.run_id,
        input.pipeline_version,
    )

    # Build a minimal IngestionConfig for Spark session construction
    ingestion_config = IngestionConfig(
        minio_endpoint=config.minio_endpoint,
        minio_access_key=config.minio_access_key,
        minio_secret_key=config.minio_secret_key,
        nessie_uri=config.nessie_uri,
        nessie_ref="main",
        iceberg_warehouse=os.environ.get(
            "ICEBERG_WAREHOUSE", "s3://iceberg-warehouse/"
        ),
        temporal_address=config.temporal_address,
        temporal_namespace=config.temporal_namespace,
        pipeline_version=config.pipeline_version,
        ingestion_run_id=input.run_id,
    )

    spark = build_spark_session(ingestion_config, app_name="biomedical-feature-worker")

    try:
        # ── Read curated tables ───────────────────────────────────────────
        articles_df = spark.table("nessie.biomedical.curated_articles")
        trials_df = spark.table("nessie.biomedical.curated_trials")

        # ── Obtain snapshot IDs for provenance ────────────────────────────
        articles_history = spark.sql(
            "SELECT snapshot_id FROM nessie.biomedical.curated_articles.snapshots "
            "ORDER BY committed_at DESC LIMIT 1"
        )
        snapshot_rows = articles_history.collect()
        snapshot_ref = (
            str(snapshot_rows[0]["snapshot_id"]) if snapshot_rows else "unknown"
        )

        logger.info(
            "compute_and_materialize_activity: snapshot_ref=%s", snapshot_ref
        )

        # ── Collect records as Python dicts ───────────────────────────────
        article_records: list[dict[str, Any]] = [
            {
                "pmid": row["pmid"],
                "title": row["title"],
                "abstract": row["abstract"],
                "publication_date": row["publication_date"],
                "journal": row["journal"],
                "snapshot_ref": snapshot_ref,
            }
            for row in articles_df.collect()
        ]

        trial_records: list[dict[str, Any]] = [
            {
                "nct_id": row["nct_id"],
                "sample_size": row["sample_size"],
                "primary_outcomes": row["primary_outcomes"],
                "status": row["status"],
                "conditions": row["conditions"],
                "snapshot_ref": snapshot_ref,
            }
            for row in trials_df.collect()
        ]

    finally:
        spark.stop()

    # ── Compute features ──────────────────────────────────────────────────
    article_features = compute_article_stats_batch(article_records)
    trial_features = compute_trial_stats_batch(trial_records)

    logger.info(
        "compute_and_materialize_activity: articles_computed=%d trials_computed=%d",
        len(article_features),
        len(trial_features),
    )

    # ── Build DataFrames and write parquet ────────────────────────────────
    now_utc = pd.Timestamp.now(tz="UTC")

    article_df = pd.DataFrame(article_features)
    article_df["event_timestamp"] = now_utc

    trial_df = pd.DataFrame(trial_features)
    trial_df["event_timestamp"] = now_utc

    tmpdir = tempfile.mkdtemp(prefix="feature_parquet_")
    article_parquet = str(Path(tmpdir) / "article_stats.parquet")
    trial_parquet = str(Path(tmpdir) / "trial_stats.parquet")

    article_df.to_parquet(article_parquet, index=False)
    trial_df.to_parquet(trial_parquet, index=False)

    logger.info(
        "compute_and_materialize_activity: parquet written to %s", tmpdir
    )

    # ── Feast: apply and materialize ──────────────────────────────────────
    store = build_feature_store(config)

    entities = get_entity_definitions()
    feature_views = get_feature_views(
        article_parquet_path=article_parquet,
        trial_parquet_path=trial_parquet,
    )

    store.apply(entities + feature_views)

    end_date = datetime.now(tz=timezone.utc)
    start_date = end_date - timedelta(days=730)

    store.materialize(start_date=start_date, end_date=end_date)

    logger.info("compute_and_materialize_activity: materialization complete")

    return FeatureRefreshOutput(
        run_id=input.run_id,
        articles_computed=len(article_features),
        trials_computed=len(trial_features),
        iceberg_snapshot_ref=snapshot_ref,
        feature_view_version="article_stats,trial_stats",
    )
