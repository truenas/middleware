from __future__ import annotations

import typing

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    if await middleware.call("system.is_enterprise"):
        await middleware.call2(middleware.services.update.set_profile, "MISSION_CRITICAL")
