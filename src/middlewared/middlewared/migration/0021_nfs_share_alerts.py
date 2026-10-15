from __future__ import annotations

import typing

from middlewared.api.current import QueryOptions
from middlewared.plugins.nfs_.share_alerts import sync_share_alerts

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


async def migrate(middleware: Middleware) -> None:
    for share in await middleware.call2(
        middleware.services.sharing.nfs.query, [], QueryOptions(extra={"retrieve_locked_info": False})
    ):
        await sync_share_alerts(middleware, share)
