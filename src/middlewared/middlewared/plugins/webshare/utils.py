from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from middlewared.service import ServiceContext
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH

if TYPE_CHECKING:
    from middlewared.main import Middleware

HOSTNAMES_KEY = "webshare_hostnames"


async def bindip_choices(context: ServiceContext) -> dict[str, str]:
    return {
        d['address']: d['address']
        for d in await context.middleware.call('interface.ip_in_use', {'static': True})
    }


def setup_directories() -> None:
    os.makedirs(WEBSHARE_BULK_DOWNLOAD_PATH, mode=0o700, exist_ok=True)
    os.makedirs(WEBSHARE_DATA_PATH, mode=0o700, exist_ok=True)


async def get_urls(context: ServiceContext) -> list[str]:
    try:
        hostnames = await context.call2(context.s.keyvalue.get, HOSTNAMES_KEY)
    except KeyError:
        hostnames = hostnames_from_config(await context.middleware.call("tn_connect.hostname.config"))

    return [f"https://{hostname}:755" for hostname in hostnames]


def hostnames_from_config(tn_connect_hostname_config: dict[str, Any]) -> list[str]:
    return sorted(list(tn_connect_hostname_config["hostname_details"].keys()))


async def tn_connect_hostname_updated(middleware: Middleware, tn_connect_hostname_config: dict[str, Any]) -> None:
    hostnames = hostnames_from_config(tn_connect_hostname_config)
    await middleware.call2(middleware.services.keyvalue.set, HOSTNAMES_KEY, hostnames)
    if not await middleware.call("service.started", "webshare"):
        return

    await middleware.call("service.control", "RELOAD", "webshare")
