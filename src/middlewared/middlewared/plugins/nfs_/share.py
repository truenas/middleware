from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    NfsShareCreate,
    NfsShareUpdate,
    QueryOptions,
    SharingNFSCreateArgs,
    SharingNFSCreateResult,
    SharingNFSDeleteArgs,
    SharingNFSDeleteResult,
    SharingNFSEntry,
    SharingNFSUpdateArgs,
    SharingNFSUpdateResult,
)
from middlewared.service import GenericSharingService, private
from middlewared.utils.types import AuditCallback

from .share_crud import SharingNFSServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("SharingNFSService",)


class SharingNFSService(GenericSharingService[SharingNFSEntry]):
    _svc_part: SharingNFSServicePart

    share_task_type = "NFS"

    class Config:
        namespace = "sharing.nfs"
        cli_namespace = "sharing.nfs"
        entry = SharingNFSEntry
        generic = True
        role_prefix = "SHARING_NFS"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = SharingNFSServicePart(self.context)

    @private
    async def human_identifier(self, share_task: SharingNFSEntry) -> str:
        return share_task.path

    @api_method(
        SharingNFSCreateArgs,
        SharingNFSCreateResult,
        audit="NFS share create",
        audit_extended=lambda data: data["path"],
        check_annotations=True,
    )
    async def do_create(self, data: NfsShareCreate) -> SharingNFSEntry:
        """
        Create a NFS Share.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        SharingNFSUpdateArgs,
        SharingNFSUpdateResult,
        audit="NFS share update",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: NfsShareUpdate,
    ) -> SharingNFSEntry:
        """
        Update NFS Share of ``id``.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        SharingNFSDeleteArgs,
        SharingNFSDeleteResult,
        audit="NFS share delete",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> Literal[True]:
        """
        Delete NFS Share of ``id``.
        """
        await self._svc_part.do_delete(audit_callback, id_)
        return True


async def pool_post_import(middleware: Middleware, pool: dict[str, Any] | None) -> None:
    """
    Makes sure to reload NFS if a pool is imported and there are shares configured for it.
    """
    if pool is None:
        middleware.create_task(middleware.call("etc.generate", "nfsd"))
        return

    path = f"/mnt/{pool['name']}"
    shares = await middleware.call2(middleware.services.sharing.nfs.query, [], QueryOptions(select=["path"]))
    if any(share.path.startswith(path) for share in shares):
        # No need to wait for this to complete
        await middleware.call2(middleware.services.service.control, "RELOAD", "nfs")


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("pool.post_import", pool_post_import, sync=True)
