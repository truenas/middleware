from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import SNMPEntry, SNMPUpdate, SNMPUpdateArgs, SNMPUpdateResult
from middlewared.common.ports import ServicePortDelegate
from middlewared.service import SystemServiceService, private

from .config import SNMPServicePart

if TYPE_CHECKING:
    from middlewared.main import Middleware

__all__ = ("SNMPService",)


class SNMPService(SystemServiceService[SNMPEntry]):
    class Config:
        cli_namespace = "service.snmp"
        entry = SNMPEntry
        generic = True
        role_prefix = "SYSTEM_GENERAL"

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self._service_part = SNMPServicePart(self.context)

    async def config(self) -> SNMPEntry:
        return await self._service_part.config()

    @api_method(SNMPUpdateArgs, SNMPUpdateResult, check_annotations=True)
    async def do_update(self, data: SNMPUpdate) -> SNMPEntry:
        """
        Update SNMP Service Configuration.

        The ``v3_*`` settings are valid and enforced only when ``v3`` is enabled.

        Enabling ``v3`` requires ``v3_username``, ``v3_authtype``, and ``v3_password``. Disabling
        ``v3`` alone retains the v3 user settings in the private config but removes the public config
        entry, blocking v3 access. Disabling ``v3`` and clearing ``v3_username`` additionally removes
        the user from the private config.
        """
        return await self._service_part.do_update(data)

    @private
    def get_snmp_users(self) -> list[str]:
        return self._service_part.get_snmp_users()


class SNMPServicePortDelegate(ServicePortDelegate):
    name = "snmp"
    namespace = "snmp"
    title = "SNMP Service"

    async def get_ports_bound_on_wildcards(self) -> list[int]:
        return [160, 161]


async def setup(middleware: Middleware) -> None:
    await middleware.call("port.register_attachment_delegate", SNMPServicePortDelegate(middleware))
