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
    port_fields = ["port"]
    bind_address_field = "bindip"

    async def config(self) -> dict[str, Any]:
        # the base class reads the config as a dict
        return (await self.middleware.call("s3.config")).model_dump()

    def bind_address(self, config: dict[str, Any]) -> str:
        # the daemon listens on one address; an empty list is every address
        return config["bindip"][0] if config["bindip"] else "0.0.0.0"


class S3CertificateAttachment(CertificateServiceAttachmentDelegate):
    CERT_FIELD = "certificate"
    HUMAN_NAME = "S3 Service"
    NAMESPACE = "s3"
    SERVICE = SERVICE
    # the daemon re-reads the certificate files on SIGHUP: a renewal rides a reload


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
    await middleware.call(
        "interface.register_listen_delegate", SystemServiceListenMultipleDelegate(middleware, "s3", "bindip")
    )
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
    middleware.register_hook("pool.post_import", _pool_post_import, sync=True)
