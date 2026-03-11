"""Entry-point for the Temporal agent worker process."""
from __future__ import annotations

import asyncio
import logging

from temporalio.client import Client
from temporalio.worker import Worker

from src.agent_worker.config import get_config
from src.agent_worker.temporal.activities import run_agent_graph_activity
from src.agent_worker.temporal.workflows import EvidenceWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

_TASK_QUEUE = "agent"


async def main() -> None:
    config = get_config()
    logger.info("Connecting to Temporal at %s …", config.temporal_address)
    client = await Client.connect(config.temporal_address)

    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[EvidenceWorkflow],
        activities=[run_agent_graph_activity],
    ):
        logger.info("Agent worker listening on task queue %r", _TASK_QUEUE)
        await asyncio.Event().wait()


if __name__ == "__main__":
    asyncio.run(main())
