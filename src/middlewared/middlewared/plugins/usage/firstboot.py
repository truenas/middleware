from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from .run import FAILED_RETRIES
from .submit import submit_stats

if TYPE_CHECKING:
    from middlewared.service import Service

logger = logging.getLogger(__name__)


async def firstboot(service: Service) -> None:
    _hash = await service.middleware.call("system.host_id")
    version = await service.middleware.call("system.version")
    retries = FAILED_RETRIES
    while retries:
        try:
            await submit_stats({"platform": "TrueNAS-SCALE", "system_hash": _hash, "firstboot": [{"version": version}]})
        except Exception as e:
            retries -= 1
            if not retries:
                logger.error("Failed to send firstboot statistics: %s", e)
        else:
            break
