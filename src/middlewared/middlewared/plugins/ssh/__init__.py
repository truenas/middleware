from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    SSHBindifaceChoicesArgs,
    SSHBindifaceChoicesResult,
    SSHEntry,
    SSHUpdate,
    SSHUpdateArgs,
    SSHUpdateResult,
)
from middlewared.common.ports import ServicePortDelegate
from middlewared.service import SystemServiceService, private

from .config import SSHServicePart
from .keys import cleanup_host_keys, generate_host_keys, save_host_keys

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ("SSHService",)


class SSHService(SystemServiceService[SSHEntry]):
    class Config:
        cli_namespace = "service.ssh"
        role_prefix = "SSH"
        entry = SSHEntry
        generic = True

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self._service_part = SSHServicePart(self.context)

    async def config(self) -> SSHEntry:
        return await self._service_part.config()

    @api_method(
        SSHBindifaceChoicesArgs, SSHBindifaceChoicesResult, roles=["NETWORK_INTERFACE_READ"], check_annotations=True
    )
    def bindiface_choices(self) -> dict[str, str]:
        """
        Available choices for the bindiface attribute of SSH service.
        """
        return dict(self.middleware.call_sync("interface.choices"))

    @api_method(SSHUpdateArgs, SSHUpdateResult, audit="Update SSH configuration", check_annotations=True)
    async def do_update(self, data: SSHUpdate) -> SSHEntry:
        """
        Update settings of SSH daemon service.

        If `bindiface` is empty it will listen for all available addresses.
        """
        return await self._service_part.do_update(data)

    @private
    def cleanup_keys(self) -> None:
        cleanup_host_keys(self.context)

    @private
    def generate_keys(self) -> None:
        generate_host_keys(self.context)

    @private
    def save_keys(self) -> None:
        save_host_keys(self.context)


class SSHServicePortDelegate(ServicePortDelegate):
    name = "ssh"
    namespace = "ssh"
    port_fields = ["tcpport"]
    title = "SSH Service"


async def setup(middleware: Middleware) -> None:
    await middleware.call("port.register_attachment_delegate", SSHServicePortDelegate(middleware))
    if await middleware.call("core.is_starting_during_boot"):
        await middleware.call2(middleware.services.ssh.cleanup_keys)
        await middleware.call2(middleware.services.ssh.generate_keys)
