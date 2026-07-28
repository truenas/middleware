from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import SharingNFSEntry
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.nfs import SharingNFSService

if TYPE_CHECKING:
    from middlewared.main import Middleware


class NFSFSAttachmentDelegate(LockableFSAttachmentDelegate[SharingNFSEntry]):
    name = 'nfs'
    title = 'NFS Share'
    service = 'nfs'
    service_class = SharingNFSService
    resource_name = 'path'

    async def restart_reload_services(self, attachments: list[SharingNFSEntry]) -> None:
        await self._service_change('nfs', 'reload')


async def setup(middleware: Middleware) -> None:
    await middleware.call('pool.dataset.register_attachment_delegate', NFSFSAttachmentDelegate(middleware))
