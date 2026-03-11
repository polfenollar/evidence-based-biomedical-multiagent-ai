"""Temporal workflows for the biomedical multi-agent pipeline."""
from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from src.agent_worker.temporal.activities import (
        AgentInput,
        AgentOutput,
        run_agent_graph_activity,
    )

_RETRY_POLICY = RetryPolicy(
    maximum_attempts=2,
    initial_interval=timedelta(seconds=5),
)

_ACTIVITY_TIMEOUT = timedelta(minutes=5)


@workflow.defn
class EvidenceWorkflow:
    """Durable Temporal workflow that executes the multi-agent reasoning graph.

    The workflow is a thin wrapper around the
    :func:`run_agent_graph_activity` activity — all business logic lives in
    the LangGraph graph inside the activity.
    """

    @workflow.run
    async def run(self, input: AgentInput) -> AgentOutput:
        output: AgentOutput = await workflow.execute_activity(
            run_agent_graph_activity,
            input,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY_POLICY,
        )
        return output
