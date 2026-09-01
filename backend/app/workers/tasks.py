import logging

import dramatiq

from app.workers.broker import broker as configured_broker

logger = logging.getLogger(__name__)
BROKER = configured_broker


@dramatiq.actor(queue_name="telemetryx")
def foundation_smoke_task() -> str:
    """A minimal worker task proving broker/worker wiring during Phase 1."""
    logger.info("foundation_smoke_task_completed")
    return "ok"
