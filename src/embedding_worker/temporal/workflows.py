"""Temporal workflows for the biomedical embedding / indexing pipeline."""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.embedding_worker.temporal.activities import (
        IndexingInput,
        IndexingOutput,
        fetch_and_embed_activity,
    )

_RETRY_POLICY = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=10),
)

_ACTIVITY_TIMEOUT = timedelta(minutes=60)


@workflow.defn
class IndexingWorkflow:
    """Orchestrates the full embedding/indexing pipeline for a single data source.

    Steps
    -----
    1. ``fetch_and_embed_activity`` — reads Iceberg table via Spark, embeds
       records, and upserts vectors to Qdrant.
    """

    @workflow.run
    async def run(self, input: IndexingInput) -> IndexingOutput:
        output: IndexingOutput = await workflow.execute_activity(
            fetch_and_embed_activity,
            input,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY_POLICY,
        )
        return output
