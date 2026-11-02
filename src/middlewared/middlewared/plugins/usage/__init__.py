from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.service import Service

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


async def _start(middleware: Middleware, event_type: str | None = None, args: Any = None) -> None:
    middleware.create_task(middleware.call2(middleware.services.usage.start))


async def setup(middleware: Middleware) -> None:
    await middleware.call("network.general.register_activity", "usage", "Anonymous usage statistics")
    middleware.event_subscribe("system.ready", _start)
    if await middleware.call("system.ready"):
        await _start(middleware)
