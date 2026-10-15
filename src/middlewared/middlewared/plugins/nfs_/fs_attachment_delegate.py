from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import SharingNFSEntry
from middlewared.common.attachment import LockableFSAttachmentDelegate

from .share import SharingNFSService
from .share_alerts import remove_share_alerts

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

    async def delete(self, attachments: list[SharingNFSEntry]) -> None:
        await super().delete(attachments)
        for attachment in attachments:
            await remove_share_alerts(self.middleware, attachment.id)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.zfs.resource.register_attachment_delegate, NFSFSAttachmentDelegate(middleware)
    )
