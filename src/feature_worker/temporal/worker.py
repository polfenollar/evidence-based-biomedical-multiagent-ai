"""Temporal worker entry point for the feature refresh pipeline.

Registers FeatureRefreshWorkflow and compute_and_materialize_activity on
the ``feature-refresh`` task queue.

Handles SIGTERM / SIGINT for graceful shutdown.
"""
from __future__ import annotations

import asyncio
import logging
import signal

from temporalio.client import Client
from temporalio.worker import Worker

from src.feature_worker.config import get_config
from src.feature_worker.temporal.activities import compute_and_materialize_activity
from src.feature_worker.temporal.workflows import FeatureRefreshWorkflow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)

TASK_QUEUE = "feature-refresh"


async def _run_worker(shutdown_event: asyncio.Event) -> None:
    config = get_config()

    logger.info("Connecting to Temporal at %s …", config.temporal_address)
    client = await Client.connect(
        config.temporal_address,
        namespace=config.temporal_namespace,
    )

    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[FeatureRefreshWorkflow],
        activities=[compute_and_materialize_activity],
    ) as worker:
        logger.info(
            "Worker started — task_queue=%s  namespace=%s",
            TASK_QUEUE,
            config.temporal_namespace,
        )
        await shutdown_event.wait()
        logger.info("Shutdown signal received — stopping worker …")


def main() -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    shutdown_event = asyncio.Event()

    def _signal_handler() -> None:
        logger.info("Signal received, initiating graceful shutdown …")
        loop.call_soon_threadsafe(shutdown_event.set)

    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, _signal_handler)

    try:
        loop.run_until_complete(_run_worker(shutdown_event))
    finally:
        loop.close()
        logger.info("Worker stopped.")


if __name__ == "__main__":
    main()
