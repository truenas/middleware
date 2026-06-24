from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    NTPServerCreate,
    NTPServerCreateArgs,
    NTPServerCreateResult,
    NTPServerDeleteArgs,
    NTPServerDeleteResult,
    NTPServerEntry,
    NTPServerUpdate,
    NTPServerUpdateArgs,
    NTPServerUpdateResult,
)
from middlewared.service import GenericCRUDService, filterable_api_method
from middlewared.utils.filter_list import filter_list

from .crud import NTPServerServicePart
from .peers import NTPPeerEntry, get_peers

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('NTPServerService',)


class NTPServerService(GenericCRUDService[NTPServerEntry]):

    class Config:
        namespace = 'system.ntpserver'
        cli_namespace = 'system.ntp_server'
        entry = NTPServerEntry
        role_prefix = 'NETWORK_GENERAL'
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = NTPServerServicePart(self.context)

    @api_method(NTPServerCreateArgs, NTPServerCreateResult, check_annotations=True)
    async def do_create(self, data: NTPServerCreate) -> NTPServerEntry:
        """
        Add an NTP Server.
        """
        return await self._svc_part.do_create(data)

    @api_method(NTPServerUpdateArgs, NTPServerUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: NTPServerUpdate) -> NTPServerEntry:
        """Update NTP server of ``id``."""
        return await self._svc_part.do_update(id_, data)

    @api_method(NTPServerDeleteArgs, NTPServerDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """Delete NTP server of ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @filterable_api_method(item=NTPPeerEntry, private=True)
    def peers(self, filters: list[Any], options: dict[str, Any]) -> Any:
        return filter_list(get_peers(self.context), filters, options)
