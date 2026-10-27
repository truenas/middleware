from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    SharingWebshareCreate,
    SharingWebshareCreateArgs,
    SharingWebshareCreateResult,
    SharingWebshareDeleteArgs,
    SharingWebshareDeleteResult,
    SharingWebshareEntry,
    SharingWebshareUpdate,
    SharingWebshareUpdateArgs,
    SharingWebshareUpdateResult,
)
from middlewared.service import GenericSharingService
from middlewared.utils.types import AuditCallback

from .sharing_crud import SharingWebsharePart

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('SharingWebshareService',)


class SharingWebshareService(GenericSharingService[SharingWebshareEntry]):
    _svc_part: SharingWebsharePart

    share_task_type = 'Webshare'

    class Config:
        namespace = 'sharing.webshare'
        cli_namespace = 'sharing.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        generic = True
        entry = SharingWebshareEntry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = SharingWebsharePart(self.context)

    @api_method(
        SharingWebshareCreateArgs, SharingWebshareCreateResult,
        audit='Webshare share create',
        audit_extended=lambda data: data['name'],
        check_annotations=True,
    )
    async def do_create(self, data: SharingWebshareCreate) -> SharingWebshareEntry:
        """
        Create a Webshare share that exposes a local ZFS path over the Webshare protocol.

        The shared ``path`` must reside under ``/mnt/`` within a ZFS pool. At most one share may set
        ``is_home_base`` to ``true`` to serve as the base path for user home directories.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        SharingWebshareUpdateArgs, SharingWebshareUpdateResult,
        audit='Webshare share update',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: SharingWebshareUpdate,
    ) -> SharingWebshareEntry:
        """
        Update the Webshare share identified by ``id``.

        Only one share may set ``is_home_base`` to ``true`` to serve as the base path for user home directories.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        SharingWebshareDeleteArgs, SharingWebshareDeleteResult,
        audit='Webshare share delete',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> None:
        """
        Delete the Webshare share identified by ``id``. This disconnects Webshare clients
        that are accessing the share.
        """
        await self._svc_part.do_delete(audit_callback, id_)
