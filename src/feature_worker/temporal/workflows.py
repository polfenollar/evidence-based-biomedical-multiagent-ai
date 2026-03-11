"""Temporal workflows for the biomedical feature refresh pipeline."""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.feature_worker.temporal.activities import (
        FeatureRefreshInput,
        FeatureRefreshOutput,
        compute_and_materialize_activity,
    )

_RETRY_POLICY = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=10),
)

_ACTIVITY_TIMEOUT = timedelta(minutes=60)


@workflow.defn
class FeatureRefreshWorkflow:
    """Orchestrates the full feature computation and materialization pipeline.

    Steps
    -----
    1. ``compute_and_materialize_activity`` — read Iceberg tables, compute
       statistics, write parquet, and materialize to the Feast online store.
    """

    @workflow.run
    async def run(self, input: FeatureRefreshInput) -> FeatureRefreshOutput:
        output: FeatureRefreshOutput = await workflow.execute_activity(
            compute_and_materialize_activity,
            input,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY_POLICY,
        )
        return output
