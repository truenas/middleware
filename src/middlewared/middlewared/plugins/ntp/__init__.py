from __future__ import annotations

from typing import Any, Literal, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    NTPServerEntry,
    NTPServerCreate,
    NTPServerCreateArgs, NTPServerCreateResult,
    NTPServerUpdate,
    NTPServerUpdateArgs, NTPServerUpdateResult,
    NTPServerDeleteArgs, NTPServerDeleteResult,
    QueryOptions,
)
from middlewared.service import CRUDService, filterable_api_method
from middlewared.utils.filter_list import filter_list

from .crud import NTPServerServicePart
from .peers import NTPPeerEntry, get_peers

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('NTPServerService',)


class NTPServerService(CRUDService[NTPServerEntry]):

    class Config:
        namespace = 'system.ntpserver'
        cli_namespace = 'system.ntp_server'
        entry = NTPServerEntry
        role_prefix = 'NETWORK_GENERAL'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = NTPServerServicePart(self.context)

    async def query(
        self, filters: list[Any] | None = None, options: dict[str, Any] | None = None
    ) -> list[NTPServerEntry] | NTPServerEntry | int:
        return await self._svc_part.query(filters or [], QueryOptions(**(options or {})))

    async def get_instance(self, id_: int, options: dict[str, Any] | None = None) -> NTPServerEntry:
        return await self._svc_part.get_instance(id_, extra=(options or {}).get('extra'))

    @api_method(NTPServerCreateArgs, NTPServerCreateResult, check_annotations=True)
    async def do_create(self, data: NTPServerCreate) -> NTPServerEntry:
        """
        Add an NTP Server.

        `address` specifies the hostname/IP address of the NTP server.

        `burst` when enabled makes sure that if server is reachable, sends a burst of eight packets instead of one.
        This is designed to improve timekeeping quality with the server command.

        `iburst` when enabled speeds up the initial synchronization, taking seconds rather than minutes.

        `prefer` marks the specified server as preferred. When all other things are equal, this host is chosen
        for synchronization acquisition with the server command. It is recommended that they be used for servers with
        time monitoring hardware.

        `minpoll` is minimum polling time in seconds. It must be a power of 2 and less than `maxpoll`.

        `maxpoll` is maximum polling time in seconds. It must be a power of 2 and greater than `minpoll`.

        `force` when enabled forces the addition of NTP server even if it is currently unreachable.
        """
        return await self._svc_part.do_create(data)

    @api_method(NTPServerUpdateArgs, NTPServerUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: NTPServerUpdate) -> NTPServerEntry:
        """Update NTP server of `id`."""
        return await self._svc_part.do_update(id_, data)

    @api_method(NTPServerDeleteArgs, NTPServerDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """Delete NTP server of `id`."""
        await self._svc_part.do_delete(id_)
        return True

    @filterable_api_method(item=NTPPeerEntry, private=True)
    def peers(self, filters: list[Any], options: dict[str, Any]) -> Any:
        return filter_list(get_peers(self.context), filters, options)
