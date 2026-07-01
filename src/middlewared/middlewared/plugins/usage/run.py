from __future__ import annotations

import asyncio
import logging
import random
from typing import TYPE_CHECKING

from middlewared.utils.time_utils import utc_now

from .gather import gather
from .submit import submit_stats

if TYPE_CHECKING:
    from middlewared.service import Service

logger = logging.getLogger(__name__)

FAILED_RETRIES = 3


async def start(service: Service) -> None:
    middleware = service.middleware
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
            # We still want to schedule the next call
            logger.error("Failed to submit usage statistics", exc_info=True)
            retries -= 1
            if retries:
                logger.debug("Retrying gathering stats after 30 minutes")
                await asyncio.sleep(1800)
        else:
            break

    event_loop = asyncio.get_event_loop()
    now = utc_now()
    scheduled = (now.replace(hour=23, minute=59, second=59) - now).total_seconds() + random.uniform(1, 86400)

    event_loop.call_later(scheduled, lambda: middleware.create_task(service.call2(service.s.usage.start)))
    logger.debug("Scheduled next run in %d seconds", round(scheduled))
