from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.common.ports import ServicePortDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class FTPServicePortDelegate(ServicePortDelegate):

    name = 'FTP'
    namespace = 'ftp'
    port_fields = ['port']
    title = 'FTP Service'


async def setup(middleware: Middleware) -> None:
    await middleware.call('port.register_attachment_delegate', FTPServicePortDelegate(middleware))
