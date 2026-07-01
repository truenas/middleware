from __future__ import annotations

import asyncio
import random
from typing import TYPE_CHECKING, Any

from middlewared.service import Service
from middlewared.utils.time_utils import utc_now

from . import firstboot as _firstboot
from . import gather as _gather
from . import run as _run

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("UsageService",)


class UsageService(Service):
    class Config:
        private = True

    async def start(self) -> None:
        await _run.start(self)

    async def firstboot(self) -> None:
        await _firstboot.firstboot(self)

    def gather(self, restrict_usage: list[str] | None = None) -> dict[str, Any]:
        """
        Collect and return the full anonymous usage statistics payload.
        """
        return _gather.gather(self, restrict_usage)


async def setup(middleware: Middleware) -> None:
    now = utc_now()
    event_loop = asyncio.get_event_loop()

    await middleware.call("network.general.register_activity", "usage", "Anonymous usage statistics")
    event_loop.call_at(
        random.uniform(1, (now.replace(hour=23, minute=59, second=59) - now).total_seconds()),
        lambda: middleware.create_task(middleware.call2(middleware.services.usage.start)),
    )
