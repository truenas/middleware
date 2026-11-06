from __future__ import annotations

import asyncio
import os
from typing import TYPE_CHECKING, Any

from middlewared.alert.source.webshare import WebshareStoppedAlert
from middlewared.api.current import QueryOptions
from middlewared.plugins.truenas_connect.utils import CONFIGURED_TNC_STATES
from middlewared.service import ServiceContext
from middlewared.utils.hardware import get_hardware_class
from middlewared.utils.service.call_mixin import CallMixin
from middlewared.utils.webshare import WEBSHARE_BULK_DOWNLOAD_PATH, WEBSHARE_DATA_PATH

if TYPE_CHECKING:
    from middlewared.main import Middleware


_reconcile_lock = asyncio.Lock()


async def reload_webshare(context: CallMixin) -> None:
    await (await context.call2(context.s.service.control, 'RELOAD', 'webshare')).wait(raise_error=True)
    await context.call2(context.s.truesearch.configure)


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
    await middleware.call2(middleware.services.service.control, "RELOAD", "webshare")


async def start_blocker(context: ServiceContext) -> str | None:
    if (await context.to_thread(get_hardware_class)).is_appliance:
        return None

    tnc_config = await context.call2(context.s.tn_connect.config)
    if tnc_config.enabled and tnc_config.status in CONFIGURED_TNC_STATES and tnc_config.certificate is not None:
        return None

    return "Webshare requires TrueNAS Connect to be configured."


async def reconcile(middleware: Middleware) -> None:
    async with _reconcile_lock:
        if not await middleware.call("failover.is_single_master_node"):
            return

        svc = await middleware.call2(
            middleware.services.service.query, [["service", "=", "webshare"]], QueryOptions(get=True),
        )
        running = svc.state == "RUNNING"
        blocker = await middleware.call2(middleware.services.webshare.start_blocker)

        if blocker is not None:
            if running:
                middleware.logger.info("webshare: stopping because %s", blocker)
                await (await middleware.call2(middleware.services.service.control, "STOP", "webshare")).wait(
                    raise_error=True,
                )
            if svc.enable:
                await middleware.call2(middleware.services.alert.oneshot_create, WebshareStoppedAlert())
            return

        await middleware.call2(middleware.services.alert.oneshot_delete, "WebshareStopped")
        if running:
            # RESTART rather than RELOAD: link-caddy also loads the TNC certificates, and the auth
            # service's reload restarts only the main caddy.
            middleware.logger.info("webshare: restarting to pick up TrueNAS Connect certificate changes")
            await (await middleware.call2(middleware.services.service.control, "RESTART", "webshare")).wait(
                raise_error=True,
            )
        elif svc.enable:
            middleware.logger.info("webshare: starting as TrueNAS Connect is configured")
            await (await middleware.call2(middleware.services.service.control, "START", "webshare")).wait(
                raise_error=True,
            )


async def tn_connect_certificate_changed(middleware: Middleware) -> None:
    await reconcile(middleware)


async def system_ready(middleware: Middleware, event_type: Any, args: Any) -> None:
    # caddy-config skips licence detection until system.ready, so the units systemd started at boot
    # hold no certificates.
    await reconcile(middleware)
