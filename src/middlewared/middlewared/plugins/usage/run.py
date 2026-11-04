from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from .gather import gather
from .submit import submit_stats

if TYPE_CHECKING:
    from middlewared.service import Service

logger = logging.getLogger(__name__)

FAILED_RETRIES = 3
SUBMIT_INTERVAL = 86400
LAST_SUBMITTED_KEY = "usage.last_submitted"


async def get_last_submitted(service: Service) -> float:
    """
    Return when the usage statistics were last submitted (epoch seconds).

    When nothing is saved yet, or the saved time is in the future because the clock moved
    backwards, the current time is saved and returned so the interval starts from now.
    """
    now = time.time()
    last: float = await service.call2(service.s.keyvalue.get, LAST_SUBMITTED_KEY, 0)
    if not last or last > now:
        await service.call2(service.s.keyvalue.set, LAST_SUBMITTED_KEY, now)
        last = now

    return last


async def submit_if_due(service: Service) -> None:
    middleware = service.middleware
    # Submit only when a full interval has passed, however many times this runs (middleware restarts, failover)
    if time.time() - await get_last_submitted(service) < SUBMIT_INTERVAL:
        return

    retries = FAILED_RETRIES
    while retries:
        if not await middleware.call("failover.is_single_master_node") or not await middleware.call(
            "network.general.can_perform_activity", "usage"
        ):
            break

        if (await middleware.call("system.general.config"))["usage_collection"]:
            restrict_usage = []
        else:
            restrict_usage = ["gather_total_capacity", "gather_system_version"]

        try:
            await submit_stats(await middleware.run_in_thread(gather, service, restrict_usage))
        except Exception:
            logger.error("Failed to submit usage statistics", exc_info=True)
            retries -= 1
            if retries:
                logger.debug("Retrying gathering stats after 30 minutes")
                await asyncio.sleep(1800)
        else:
            await service.call2(service.s.keyvalue.set, LAST_SUBMITTED_KEY, time.time())
            break


async def start(service: Service) -> None:
    middleware = service.middleware
    scheduled: float = SUBMIT_INTERVAL
    try:
        await submit_if_due(service)
        # A full interval after the last submission, or from now when this run was overdue but did not submit
        scheduled = max(await get_last_submitted(service) + SUBMIT_INTERVAL - time.time(), 0) or SUBMIT_INTERVAL
    except Exception:
        logger.error("Failed to run usage statistics submission", exc_info=True)

    event_loop = asyncio.get_event_loop()
    event_loop.call_later(scheduled, lambda: middleware.create_task(service.call2(service.s.usage.start)))
    logger.debug("Scheduled next run in %d seconds", round(scheduled))
