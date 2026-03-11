"""Temporal workflows for the biomedical ingestion pipeline."""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError

with workflow.unsafe.imports_passed_through():
    from src.ingestion_worker.temporal.activities import (
        IngestionInput,
        IngestionOutput,
        parse_and_validate_activity,
        write_to_lake_activity,
    )

_RETRY_POLICY = RetryPolicy(
    maximum_attempts=3,
    initial_interval=timedelta(seconds=5),
)

_ACTIVITY_TIMEOUT = timedelta(minutes=30)


@workflow.defn
class IngestionWorkflow:
    """Orchestrates the full ingestion pipeline for a single data source.

    Steps
    -----
    1. ``parse_and_validate_activity`` — load file, parse records, run DQ.
    2. If DQ blocking failures are present → raise ApplicationError.
    3. ``write_to_lake_activity`` — write raw + curated Iceberg tables.
    """

    @workflow.run
    async def run(self, input: IngestionInput) -> IngestionOutput:
        # ── Step 1: parse and validate ──────────────────────────────────
        parse_result: dict = await workflow.execute_activity(
            parse_and_validate_activity,
            input,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY_POLICY,
        )

        # ── Step 2: check for blocking DQ failures ─────────────────────
        if not parse_result.get("dq_passed", True):
            raise ApplicationError(
                f"DQ blocking failures for run_id={input.run_id} "
                f"source={input.source_name}. "
                f"DQ report: {parse_result.get('dq_report')}",
                type="DQBlockingFailure",
                non_retryable=True,
            )

        # ── Step 3: write to lake ───────────────────────────────────────
        output: IngestionOutput = await workflow.execute_activity(
            write_to_lake_activity,
            parse_result,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY_POLICY,
        )

        return output
