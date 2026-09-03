"""The TrueNAS S3 service plugin family.

`s3` is the global service configuration and holds `s3.accesskey`, the
SigV4 credential pairs; `sharing.s3` is the bucket, the share-like
entity. Every change funnels through `s3.reconfigure`, which renders the
daemon's files and reloads or restarts it as the diff requires.
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from middlewared.common.attachment.certificate import CertificateServiceAttachmentDelegate
from middlewared.common.listen import SystemServiceListenMultipleDelegate
from middlewared.common.ports import ServicePortDelegate

from .accesskey_crud import S3AccesskeyService
from .bucket_crud import SharingS3Service
from .config import S3Service
from .lifecycle import SERVICE, start_or_restart

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("S3Service", "S3AccesskeyService", "SharingS3Service")


class S3ServicePortDelegate(ServicePortDelegate):
    name = "s3"
    namespace = "s3"
    title = "S3 Service"
    port_fields = ["listeners"]

    async def config(self) -> dict[str, Any]:
        # the base class reads the config as a dict
        return (await self.middleware.call("s3.config")).model_dump()

    async def get_ports_internal(self) -> list[tuple[str, int]]:
        # every listener is a bound port; none is every address on 9000
        config = await self.config()
        return [(each["address"], each["port"]) for each in config["listeners"]] or [("0.0.0.0", 9000)]


class S3ListenDelegate(SystemServiceListenMultipleDelegate):
    """What an interface losing a static address does to the listeners
    naming it: the base reads a list of addresses, this reads the
    address out of each listener."""

    async def get_listen_state(self, ips: list[str]) -> list[dict[str, Any]]:
        return (await self.middleware.call("s3.config")).model_dump()["listeners"]

    async def listens_on(self, state: list[dict[str, Any]], ip: str) -> bool:
        return any(listener["address"] == ip for listener in state)


class S3CertificateAttachment(CertificateServiceAttachmentDelegate):
    CERT_FIELD = "certificate"
    HUMAN_NAME = "S3 Service"
    NAMESPACE = "s3"
    SERVICE = SERVICE
    # the daemon rotates the pair on a reload: a renewal rides one

    async def state(self, cert_id: int) -> bool:
        # a chosen certificate is held whether or not a listener serves it
        # yet; the UI's is held only while none is chosen and one does
        config = (await self.middleware.call("s3.config")).model_dump()
        if config["certificate"] is not None:
            return config["certificate"] == cert_id
        if not any(listener["tls"] for listener in config["listeners"]):
            return False
        return await self.middleware.call("s3.effective_certificate", None) == cert_id


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
    # a service following the UI certificate follows it here: the files
    # a different certificate renders to are other paths, which the
    # daemon rotates to on reload
    s3 = (await middleware.call("s3.config")).model_dump()
    if s3["certificate"] is None and any(listener["tls"] for listener in s3["listeners"]):
        await _reconfigure(middleware)


async def _pool_post_import(middleware: Middleware, pool: dict[str, Any] | None) -> None:
    if pool is None:
        # the boot-time bulk import renders the etc group through its own
        # checkpoint, and the unit starts on its own
        return
    prefix = f"{pool['name']}/"
    buckets = await middleware.call("sharing.s3.query", [["enabled", "=", True]])
    if any(b.dataset == pool["name"] or b.dataset.startswith(prefix) for b in buckets):
        # rows coming back into the registry are a change the daemon refuses
        # on a reload
        try:
            await start_or_restart(middleware)
        except Exception:
            middleware.logger.error("s3: failed to restart after importing pool %s", pool["name"], exc_info=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call("port.register_attachment_delegate", S3ServicePortDelegate(middleware))
    await middleware.call("certificate.register_attachment_delegate", S3CertificateAttachment(middleware))
    await middleware.call("interface.register_listen_delegate", S3ListenDelegate(middleware, "s3", "listeners"))
    # an access key change re-renders the credentials file; an account change
    # can move a resolved name or turn a key into USER_MISSING, and a stale
    # file at the daemon's next load would refuse the whole credentials file
    for hook in (
        "s3.accesskey.post_create",
        "s3.accesskey.post_update",
        "s3.accesskey.post_delete",
        "user.post_update",
        "group.post_update",
        "group.post_delete",
    ):
        middleware.register_hook(hook, _reconfigure, sync=True)
    middleware.register_hook("user.post_delete", _user_deleted, sync=True)
    middleware.register_hook("system.general.post_update", _ui_settings_updated, sync=True)
    middleware.register_hook("pool.post_import", _pool_post_import, sync=True)
