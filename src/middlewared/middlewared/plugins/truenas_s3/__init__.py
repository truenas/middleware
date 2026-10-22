from __future__ import annotations

import ipaddress
from typing import Any, TYPE_CHECKING

from middlewared.api.current import S3Entry
from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate
from middlewared.common.license_reconcile import LicenseReconcileAction, LicenseReconcileDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.common.ports import ServicePortDelegate

from .accesskey_crud import S3AccesskeyService
from .bucket_crud import SharingS3Service
from .config import S3Service
from .lifecycle import ETC_GROUP, SERVICE, start_or_restart

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("S3Service", "S3AccesskeyService", "SharingS3Service")


# the delegate bases declare their class attributes as NotImplemented
# sentinels, so every concrete value is an override of the sentinel's type
class S3ServicePortDelegate(ServicePortDelegate):
    name = "s3"  # type: ignore[assignment]
    namespace = "s3"  # type: ignore[assignment]
    title = "S3 Service"  # type: ignore[assignment]
    port_fields = ["listeners"]  # type: ignore[assignment]

    async def config(self) -> dict[str, Any]:
        # the base class reads the config as a dict
        config: S3Entry = await self.middleware.call("s3.config")
        return config.model_dump()

    async def get_ports_internal(self) -> list[tuple[str, int]]:
        # every listener is a bound port; none is every address on 9000
        config = await self.config()
        return [(each["address"], each["port"]) for each in config["listeners"]] or [("0.0.0.0", 9000)]


def _wildcard_listeners(state: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Wildcard listeners for a reset: one per address family and port,
    keeping TLS where it was served."""
    wanted: dict[tuple[str, int], bool] = {}
    for listener in state:
        v6 = ipaddress.ip_address(listener["address"]).version == 6
        key = ("::" if v6 else "0.0.0.0", listener["port"])
        wanted[key] = wanted.get(key, False) or listener["tls"]
    return [{"address": address, "port": port, "tls": tls} for (address, port), tls in sorted(wanted.items())]


class S3ListenDelegate(SystemServiceListenMultipleDelegate):
    """Resets listeners that name an address an interface lost to wildcards
    that keep each port's TLS."""

    async def get_listen_state(self, ips: list[str]) -> list[dict[str, Any]]:
        config: S3Entry = await self.middleware.call("s3.config")
        return [listener.model_dump() for listener in config.listeners]

    async def listens_on(self, state: list[dict[str, Any]], ip: str) -> bool:
        return any(listener["address"] == ip for listener in state)

    async def reset_listens(self, state: list[dict[str, Any]]) -> None:
        await self.set_listen_state(_wildcard_listeners(state))  # type: ignore[no-untyped-call]



class S3LicenseReconcileDelegate(LicenseReconcileDelegate):
    """Restart the S3 service on a license change. The daemon reads the
    license once at start, so a reload does not pick up a new one. Runs only
    while the service is up."""

    name = "s3"
    etc_groups = (ETC_GROUP,)
    service = SERVICE
    action = LicenseReconcileAction.RESTART
    # after `user`: the credentials file resolves every account through NSS
    order = 30

    async def should_run(self, middleware: Middleware) -> bool:
        svc = await middleware.call("service.query", [["service", "=", SERVICE]], {"get": True})
        return svc["state"].lower() == "running"  # type: ignore[no-any-return]


class S3CertificateAttachment(CertificateServiceAttachmentDelegate):
    CERT_FIELD = "certificate"
    HUMAN_NAME = "S3 Service"  # type: ignore[assignment]
    NAMESPACE = "s3"  # type: ignore[assignment]
    SERVICE = SERVICE  # type: ignore[assignment]
    # the daemon rotates the pair on a reload: a renewal rides one

    async def state(self, cert_id: int) -> bool:
        # hold the chosen certificate, or the UI's while none is chosen
        config: S3Entry = await self.middleware.call("s3.config")
        if config.certificate is not None:
            return config.certificate == cert_id
        if not any(listener.tls for listener in config.listeners):
            return False
        effective: int | None = await self.middleware.call("s3.effective_certificate", None)
        return effective == cert_id


async def _reconfigure(middleware: Middleware, *_args: Any, **_kwargs: Any) -> None:
    try:
        await middleware.call("s3.reconfigure")
    except Exception:
        middleware.logger.error("s3: failed to apply the configuration change", exc_info=True)


async def _user_deleted(middleware: Middleware, user_id: int) -> None:
    # a local account's keys go with it, then the credentials file follows
    try:
        await middleware.call("s3.accesskey.delete_for_user", user_id)
    except Exception:
        middleware.logger.error("s3: failed to remove the access keys of deleted user %d", user_id, exc_info=True)
    await _reconfigure(middleware)


async def _ui_settings_updated(middleware: Middleware, config: dict[str, Any]) -> None:
    # a different certificate renders to other paths, which the daemon rotates to on reload
    s3: S3Entry = await middleware.call("s3.config")
    if s3.certificate is None and any(listener.tls for listener in s3.listeners):
        await _reconfigure(middleware)


async def _pool_post_import(middleware: Middleware, pool: dict[str, Any] | None) -> None:
    if pool is None:
        # the boot-time import renders the etc group through its own checkpoint
        return
    prefix = f"{pool['name']}/"
    buckets = await middleware.call("sharing.s3.query", [["enabled", "=", True]])
    if any(b.dataset == pool["name"] or b.dataset.startswith(prefix) for b in buckets):
        # rows returning to the registry need a restart
        try:
            await start_or_restart(middleware)
        except Exception:
            middleware.logger.error("s3: failed to restart after importing pool %s", pool["name"], exc_info=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call(
        "port.register_attachment_delegate",
        S3ServicePortDelegate(middleware),  # type: ignore[no-untyped-call]
    )
    await middleware.call(
        "certificate.register_attachment_delegate",
        S3CertificateAttachment(middleware),  # type: ignore[no-untyped-call]
    )
    await middleware.call(
        "interface.register_listen_delegate",
        S3ListenDelegate(middleware, "s3", "listeners"),  # type: ignore[no-untyped-call]
    )
    await middleware.call2(
        middleware.services.truenas.license.register_reconcile_delegate,
        S3LicenseReconcileDelegate(),
    )
    # access key, account and network changes all move what the credentials file or base_hosts render
    for hook in (
        "s3.accesskey.post_create",
        "s3.accesskey.post_update",
        "s3.accesskey.post_delete",
        "user.post_update",
        "group.post_update",
        "group.post_delete",
        "network.configuration.post_update",
    ):
        middleware.register_hook(hook, _reconfigure, sync=True)
    middleware.register_hook("user.post_delete", _user_deleted, sync=True)
    middleware.register_hook("system.general.post_update", _ui_settings_updated, sync=True)
    middleware.register_hook("pool.post_import", _pool_post_import, sync=True)
