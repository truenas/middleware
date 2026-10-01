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
from middlewared.service import GenericCRUDService, filterable_api_method, private
from middlewared.utils.filter_list import filter_list
from middlewared.utils.types import AuditCallback

from .crud import NTPServerServicePart
from .peers import NTPPeerEntry, NTSAuthData, get_nts_authdata, get_peers

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

    @api_method(
        NTPServerCreateArgs,
        NTPServerCreateResult,
        audit='NTP server create',
        audit_extended=lambda data: data['address'],
        check_annotations=True,
    )
    async def do_create(self, data: NTPServerCreate) -> NTPServerEntry:
        """
        Add an NTP Server.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        NTPServerUpdateArgs,
        NTPServerUpdateResult,
        audit='NTP server update',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(self, audit_callback: AuditCallback, id_: int, data: NTPServerUpdate) -> NTPServerEntry:
        """Update NTP server of ``id``."""
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        NTPServerDeleteArgs,
        NTPServerDeleteResult,
        audit='NTP server delete',
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> Literal[True]:
        """Delete NTP server of ``id``."""
        await self._svc_part.do_delete(audit_callback, id_)
        return True

    @filterable_api_method(item=NTPPeerEntry, private=True)
    def peers(self, filters: list[Any], options: dict[str, Any]) -> Any:
        return filter_list(get_peers(self.context), filters, options)

    @private
    def nts_authdata(self) -> list[NTSAuthData]:
        return get_nts_authdata(self.context)

    @private
    async def domain_clock_advice(self) -> str:
        return await self._svc_part.domain_clock_advice()
