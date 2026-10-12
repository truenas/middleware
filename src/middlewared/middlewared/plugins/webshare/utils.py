from __future__ import annotations

import os
from typing import TYPE_CHECKING

from middlewared.service import ServiceContext
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH

if TYPE_CHECKING:
    from middlewared.main import Middleware


async def bindip_choices(context: ServiceContext) -> dict[str, str]:
    return {
        d['address']: d['address']
        for d in await context.middleware.call('interface.ip_in_use', {'static': True})
    }


def setup_directories() -> None:
    os.makedirs(WEBSHARE_BULK_DOWNLOAD_PATH, mode=0o700, exist_ok=True)
    os.makedirs(WEBSHARE_DATA_PATH, mode=0o700, exist_ok=True)


async def get_urls(context: ServiceContext) -> list[str]:
    hostnames = await context.call2(context.s.tn_connect.hostname.details)
    return [f"https://{hostname}:755" for hostname in sorted(hostnames)]


async def tn_connect_hostname_updated(middleware: Middleware) -> None:
    if not await middleware.call2(middleware.services.service.started, "webshare"):
        return

    await middleware.call2(middleware.services.service.control, "RELOAD", "webshare")
