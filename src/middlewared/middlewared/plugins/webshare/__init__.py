from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    WebshareBindipChoicesArgs,
    WebshareBindipChoicesResult,
    WebshareEntry,
    WebshareUpdate,
    WebshareUpdateArgs,
    WebshareUpdateResult,
)
from middlewared.service import GenericConfigService, private

from .config import WebshareConfigPart
from .utils import (
    bindip_choices,
    get_urls,
    system_ready,
    tn_connect_certificate_changed,
    tn_connect_hostname_updated,
)
from .utils import (
    setup_directories as _setup_directories,
)
from .utils import (
    start_blocker as _start_blocker,
)

if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('WebshareService',)


class WebshareService(GenericConfigService[WebshareEntry]):

    class Config:
        service = 'webshare'
        service_verb = 'reload'
        cli_namespace = 'service.webshare'
        role_prefix = 'SHARING_WEBSHARE'
        generic = True
        entry = WebshareEntry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = WebshareConfigPart(self.context)

    @api_method(
        WebshareUpdateArgs, WebshareUpdateResult,
        audit='Update Webshare configuration', check_annotations=True,
    )
    async def do_update(self, data: WebshareUpdate) -> WebshareEntry:
        """Update Webshare Service Configuration."""
        old = await self.config()
        new = await self._svc_part.do_update(data)

        if old.search != new.search:
            await self.call2(self.s.truesearch.configure)

        await self._service_change(self._config.service, 'reload')

        return new

    @api_method(WebshareBindipChoicesArgs, WebshareBindipChoicesResult, check_annotations=True)
    async def bindip_choices(self) -> dict[str, str]:
        """Returns ip choices for Webshare service to use."""
        return await bindip_choices(self.context)

    @private
    def setup_directories(self) -> None:
        _setup_directories()

    @private
    async def urls(self) -> list[str]:
        return await get_urls(self.context)

    @private
    async def start_blocker(self) -> str | None:
        return await _start_blocker(self.context)


async def setup(middleware: Middleware) -> None:
    middleware.register_hook("tn_connect.hostname.updated", tn_connect_hostname_updated)
    middleware.register_hook("tn_connect.certificate.changed", tn_connect_certificate_changed)
    middleware.event_subscribe("system.ready", system_ready)
