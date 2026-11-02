from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api.current import SharingWebshareEntry
from middlewared.common.attachment import LockableFSAttachmentDelegate

from .sharing import SharingWebshareService
from .utils import reload_webshare

if TYPE_CHECKING:
    from middlewared.main import Middleware


class WebshareFSAttachmentDelegate(LockableFSAttachmentDelegate[SharingWebshareEntry]):
    name = "webshare"
    title = "Webshare Share"
    service = "webshare"
    service_class = SharingWebshareService

    async def restart_reload_services(self, attachments: list[SharingWebshareEntry]) -> None:
        await reload_webshare(self)


async def setup(middleware: Middleware) -> None:
    await middleware.call2(
        middleware.services.zfs.resource.register_attachment_delegate,
        WebshareFSAttachmentDelegate(middleware),
    )
