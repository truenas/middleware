from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    UPSEntry, UPSUpdateArgs, UPSUpdateResult, UPSUpdate,
    UPSDriverChoicesArgs, UPSDriverChoicesResult,
    UPSPortChoicesArgs, UPSPortChoicesResult,
)
from middlewared.service import private, SystemServiceService

from .config import UPSServicePart
from .upssched_event import handle_upssched_event
from .utils import alerts_mapping, driver_choices, port_choices


if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('UPSService',)


class UPSService(SystemServiceService[UPSEntry]):

    class Config:
        cli_namespace = 'service.ups'
        role_prefix = 'SYSTEM_GENERAL'
        entry = UPSEntry
        generic = True

    def __init__(self, middleware: Middleware):
        super().__init__(middleware)
        self._service_part = UPSServicePart(self.context)

    async def config(self) -> UPSEntry:
        return await self._service_part.config()

    @api_method(UPSUpdateArgs, UPSUpdateResult, check_annotations=True)
    async def do_update(self, data: UPSUpdate) -> UPSEntry:
        """
        Update UPS Service Configuration.

        `powerdown` when enabled, sets UPS to power off after shutting down the system.

        `nocommwarntime` is a value in seconds which makes UPS Service wait the specified seconds before alerting that
        the Service cannot reach configured UPS.

        `shutdowntimer` is a value in seconds which tells the Service to wait specified seconds for the UPS before
        initiating a shutdown. This only applies when `shutdown` is set to "BATT".

        `shutdowncmd` is the command which is executed to initiate a shutdown. It defaults to "poweroff".
        """
        return await self._service_part.do_update(data)

    @api_method(UPSDriverChoicesArgs, UPSDriverChoicesResult, check_annotations=True, roles=['SYSTEM_GENERAL_READ'])
    def driver_choices(self) -> dict[str, str]:
        """
        Returns choices of UPS drivers supported by the system.
        """
        return driver_choices()

    @api_method(UPSPortChoicesArgs, UPSPortChoicesResult, roles=['SYSTEM_GENERAL_READ'], check_annotations=True)
    def port_choices(self) -> list[str]:
        """
        Returns available UPS device ports for the system (serial ports, USB HID devices, and "auto").
        """
        adv_config = self.middleware.call_sync('system.advanced.config')
        return port_choices(adv_config['serialconsole'], adv_config['serialport'])

    @private
    async def dismiss_alerts(self) -> None:
        alerts = list(alerts_mapping().values())
        await self.middleware.call('alert.oneshot_delete', alerts)

    @private
    async def upssched_event(self, notify_type: str) -> None:
        await handle_upssched_event(self.context, notify_type)


async def setup(middleware: Middleware) -> None:
    # Let's delete all UPS related alerts when starting middlewared ensuring we don't have any leftovers
    await middleware.call('ups.dismiss_alerts')
