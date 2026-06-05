from __future__ import annotations

import contextlib
import logging
from typing import Any

from truenas_connect_utils.config import get_account_id_and_system_id
from truenas_connect_utils.status import Status
from truenas_connect_utils.urls import get_account_service_url

from middlewared.alert.source.truenas_connect import TNCDisabledAutoUnconfiguredAlert
from middlewared.api.current import TrueNASConnectEntry
from middlewared.service import CallError, ServiceContext

from .request import auth_headers, tnc_request
from .utils import CLAIM_TOKEN_CACHE_KEY, TNC_IPS_CACHE_KEY, get_unset_payload

logger = logging.getLogger("truenas_connect")

DATASTORE = "truenas_connect"


async def config_internal(context: ServiceContext) -> dict[str, Any]:
    # Returns dict (not Pydantic) — callers need jwt_token + raw registration_details
    # which the public Entry strips/transforms in extend().
    entry: TrueNASConnectEntry = await context.call2(context.s.tn_connect.config)
    raw: dict[str, Any] = await context.middleware.call("datastore.config", DATASTORE)
    return raw | entry.model_dump()


async def set_status(
    context: ServiceContext,
    new_status: str,
    db_payload: dict[str, Any] | None = None,
) -> None:
    assert new_status in Status.__members__
    entry = await context.call2(context.s.tn_connect.config)
    await context.middleware.call(
        "datastore.update",
        DATASTORE,
        entry.id,
        {"status": new_status} | (db_payload or {}),
    )
    new_entry = await context.call2(context.s.tn_connect.config)
    context.middleware.send_event(
        "tn_connect.config",
        "CHANGED",
        fields=new_entry.model_dump(),
    )


async def unset_registration_details(
    context: ServiceContext,
    revoke_cert_and_account: bool = True,
) -> None:
    logger.debug("Unsetting registration details")
    for k in (CLAIM_TOKEN_CACHE_KEY, TNC_IPS_CACHE_KEY):
        with contextlib.suppress(KeyError):
            await context.middleware.call("cache.pop", k)

    logger.debug("TNC is being disabled, removing any stale TNC heartbeat failure alert")
    await context.call2(context.s.alert.oneshot_delete, "TNCHeartbeatConnectionFailure")

    config = await config_internal(context)
    creds = get_account_id_and_system_id(config)
    if creds is None:
        return

    if revoke_cert_and_account is False:
        # This happens when we get 401 from heartbeat as TNC will already have caatered to these cases
        logger.debug("Skipping revoking TNC user account")
        return

    logger.debug("Revoking existing TNC cert")
    await context.call2(context.s.tn_connect.acme.revoke_cert)

    logger.debug("Revoking TNC user account")
    # We need to revoke the user account now
    response = await tnc_request(
        get_account_service_url(config).format(**creds),
        "delete",
        headers=auth_headers(config),
        get_response=False,
    )
    if response["error"]:
        if response["status_code"] == 401:
            # This can happen when user removed NAS from TNC UI, so we still want unset to proceed
            logger.error("Failed to revoke account with 401 status code: %s", response["error"])
        else:
            raise CallError(f"Failed to revoke account: {response['error']}")


async def delete_cert(context: ServiceContext, cert_id: int) -> None:
    # We will like to remove the TNC cert now when TNC is disabled
    # We will not make this fatal in case user had it configured with some other plugin
    # before we had added validation to prevent users from doing that
    logger.debug("Deleting TNC certificate with id %d", cert_id)
    delete_job = await context.call2(context.s.certificate.delete, cert_id, True)
    await delete_job.wait()
    if delete_job.error:
        logger.error("Failed to delete TNC certificate: %s", delete_job.error)


async def handle_tnc_deregistration(context: ServiceContext) -> None:
    # Canonical handler for "TNC told us we are deregistered" (HTTP 401). This is the only path
    # that auto-unsets TNC and removes its certificate, so both the heartbeat (on a 401 response)
    # and the renewal check (on a 401 from the ACME config fetch) route through it.
    # Idempotent: a no-op once TNC is already unset, so concurrent callers are safe.
    tnc_config = await config_internal(context)
    if tnc_config["status"] == Status.DISABLED.name and tnc_config["certificate"] is None:
        logger.debug("TNC already deregistered/unset, nothing to do")
        return

    logger.debug("Handling TNC deregistration (401), unsetting TNC")
    with contextlib.suppress(Exception):
        # Make sure we set up a self-signed certificate and clear any alerts as we are going to
        # unset TNC. revoke_cert_and_account is False because TNC has already catered to these
        # cases on its end (the 401 means it no longer knows about us).
        await unset_registration_details(context, False)

    await context.middleware.call("datastore.update", DATASTORE, tnc_config["id"], {
        "enabled": False,
    } | get_unset_payload())
    new_entry = await context.call2(context.s.tn_connect.config)
    context.middleware.send_event("tn_connect.config", "CHANGED", fields=new_entry.model_dump())
    await context.call2(context.s.alert.oneshot_create, TNCDisabledAutoUnconfiguredAlert())

    if tnc_config["certificate"] is not None:
        await delete_cert(context, tnc_config["certificate"])


async def ha_vips(context: ServiceContext) -> list[str]:
    vips: list[str] = []
    for interface in await context.middleware.call("interface.query"):
        for vip_entry in interface.get("failover_virtual_aliases", []):
            vips.append(vip_entry["address"])
    return vips


async def get_effective_ips(context: ServiceContext) -> list[str]:
    """
    Derive the IPs TNC should advertise from system.general UI binding config.

    - If ui_address contains '0.0.0.0' (wildcard), resolve to all IPv4 addresses on the system.
    - If ui_v6address contains '::' (wildcard), resolve to all non-link-local IPv6 addresses.
    - Otherwise, use the specific addresses configured in system.general directly.
    """
    config = await context.middleware.call("system.general.config")
    ips: list[str] = []

    if "0.0.0.0" in config["ui_address"]:
        ips.extend(
            ip["address"]
            for ip in await context.middleware.call(
                "interface.ip_in_use",
                {
                    "ipv4": True,
                    "ipv6": False,
                    "ipv6_link_local": False,
                    "static": False,
                    "loopback": False,
                    "any": False,
                },
            )
        )
    else:
        ips.extend(config["ui_address"])

    if "::" in config["ui_v6address"]:
        ips.extend(
            ip["address"]
            for ip in await context.middleware.call(
                "interface.ip_in_use",
                {
                    "ipv4": False,
                    "ipv6": True,
                    "ipv6_link_local": False,
                    "static": False,
                    "loopback": False,
                    "any": False,
                },
            )
        )
    else:
        ips.extend(config["ui_v6address"])

    return ips
