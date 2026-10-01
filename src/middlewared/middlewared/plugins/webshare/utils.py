from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Literal

from truenas_connect_utils.status import Status
from truenas_pylicensed.features import LicenseFeature

from middlewared.api.current import QueryOptions
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
        hostnames = hostnames_from_config(await context.call2(context.s.tn_connect.hostname.config))

    return [f"https://{hostname}:755" for hostname in hostnames]


def hostnames_from_config(tn_connect_hostname_config: dict[str, Any]) -> list[str]:
    return sorted(list(tn_connect_hostname_config["hostname_details"].keys()))


async def tn_connect_hostname_updated(middleware: Middleware, tn_connect_hostname_config: dict[str, Any]) -> None:
    hostnames = hostnames_from_config(tn_connect_hostname_config)
    await middleware.call2(middleware.services.keyvalue.set, HOSTNAMES_KEY, hostnames)
    if not await middleware.call2(middleware.services.service.started, "webshare"):
        return

    await middleware.call2(middleware.services.service.control, "RELOAD", "webshare")


async def run_blocker(middleware: Middleware) -> str | None:
    entitlement = await middleware.call2(middleware.services.truenas.entitlements.check, LicenseFeature.WEBSHARE)
    if not entitlement.entitled:
        return entitlement.message

    if not await middleware.call2(middleware.services.tn_connect.is_configured):
        return "Webshare requires TrueNAS Connect to be configured"

    return None


async def required_action(middleware: Middleware) -> Literal["START", "STOP"] | None:
    service = await middleware.call2(
        middleware.services.service.query, [("service", "=", "webshare")], QueryOptions(get=True),
    )
    running = service.state == "RUNNING"
    if await run_blocker(middleware):
        return "STOP" if running else None

    if running or not service.enable or not await middleware.call("failover.is_single_master_node"):
        return None

    return "START"


async def sync_service_state(middleware: Middleware, *, restart_if_running: bool) -> None:
    verb: Literal["START", "STOP", "RESTART"] | None
    try:
        verb = await required_action(middleware)
        if verb is None:
            if not restart_if_running or not await middleware.call2(middleware.services.service.started, "webshare"):
                return
            # A reload does not make every WebShare listener re-read its certificates; a restart does.
            middleware.logger.info("webshare: restarting service to reload certificates")
            verb = "RESTART"
        else:
            middleware.logger.info("webshare: %s service", verb)

        await (await middleware.call2(middleware.services.service.control, verb, "webshare")).wait(raise_error=True)
    except Exception:
        middleware.logger.error("webshare: failed to sync service state", exc_info=True)


async def tn_connect_config_changed(middleware: Middleware, event_type: str, args: dict[str, Any]) -> None:
    await sync_service_state(
        middleware, restart_if_running=args["fields"]["status"] == Status.CERT_RENEWAL_SUCCESS.name,
    )


async def system_ready(middleware: Middleware, event_type: str, args: Any) -> None:
    if await middleware.call("failover.licensed"):
        return

    # systemd starts it at boot before middleware can tell it which certificates to serve.
    await sync_service_state(middleware, restart_if_running=True)
