"""Temporal activities for the biomedical embedding / indexing pipeline."""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from temporalio import activity

from src.embedding_worker.config import get_config
from src.embedding_worker.embedder import Embedder
from src.embedding_worker.jobs import index_articles, index_trials
from src.embedding_worker.qdrant_ops import QdrantOps


@dataclass
class IndexingInput:
    source_name: str       # "articles" | "trials"
    run_id: str
    pipeline_version: str


@dataclass
class IndexingOutput:
    run_id: str
    source_name: str
    vectors_indexed: int
    collection_name: str
    snapshot_ref: str
    indexing_run_id: str


@activity.defn
async def fetch_and_embed_activity(input: IndexingInput) -> IndexingOutput:
    """Fetch curated records from Iceberg via Spark, embed them, and index into Qdrant.

    Parameters
    ----------
    input:
        :class:`IndexingInput` describing the source and run metadata.

    Returns
    -------
    IndexingOutput
        Summary of the indexing run.
    """
    # Import Spark dependencies here to avoid importing them at module load
    # time in environments where PySpark is not available (e.g. unit tests).
    from src.ingestion_worker.config import get_config as get_ingestion_config  # noqa: PLC0415
    from src.ingestion_worker.spark.session import build_spark_session  # noqa: PLC0415
    from src.embedding_worker.spark_reader import (  # noqa: PLC0415
        get_snapshot_id,
        read_curated_articles,
        read_curated_trials,
    )

    logger = activity.logger
    config = get_config()
    ingestion_config = get_ingestion_config()

    logger.info(
        "fetch_and_embed_activity: source=%s run_id=%s",
        input.source_name,
        input.run_id,
    )

    indexing_run_id = str(uuid.uuid4())
    spark = build_spark_session(ingestion_config, app_name="biomedical-embedding")

    try:
        if input.source_name == "articles":
            table = "nessie.biomedical.curated_articles"
            records = read_curated_articles(spark)
            snapshot_ref = get_snapshot_id(spark, table)
        elif input.source_name == "trials":
            table = "nessie.biomedical.curated_trials"
            records = read_curated_trials(spark)
            snapshot_ref = get_snapshot_id(spark, table)
        else:
            raise ValueError(f"Unknown source_name: {input.source_name!r}")
    finally:
        spark.stop()

    logger.info(
        "fetch_and_embed_activity: records_read=%d snapshot_ref=%s",
        len(records),
        snapshot_ref,
    )

    embedder = Embedder(
        model_name=config.embedding_model,
        model_version=config.embedding_model_version,
    )
    qdrant = QdrantOps(url=config.qdrant_url)

    if input.source_name == "articles":
        from src.embedding_worker.jobs import ARTICLES_COLLECTION  # noqa: PLC0415

        count = index_articles(
            records=records,
            snapshot_ref=snapshot_ref,
            indexing_run_id=indexing_run_id,
            embedder=embedder,
            qdrant=qdrant,
            config=config,
        )
        collection_name = ARTICLES_COLLECTION
    else:
        from src.embedding_worker.jobs import TRIALS_COLLECTION  # noqa: PLC0415

        count = index_trials(
            records=records,
            snapshot_ref=snapshot_ref,
            indexing_run_id=indexing_run_id,
            embedder=embedder,
            qdrant=qdrant,
            config=config,
        )
        collection_name = TRIALS_COLLECTION

    logger.info(
        "fetch_and_embed_activity: vectors_indexed=%d collection=%s",
        count,
        collection_name,
    )

    return IndexingOutput(
        run_id=input.run_id,
        source_name=input.source_name,
        vectors_indexed=count,
        collection_name=collection_name,
        snapshot_ref=snapshot_ref,
        indexing_run_id=indexing_run_id,
    )
