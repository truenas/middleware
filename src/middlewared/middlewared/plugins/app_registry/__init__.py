from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    AppRegistryCreate, AppRegistryEntry, AppRegistryUpdate,
    AppRegistryCreateArgs, AppRegistryCreateResult,
    AppRegistryUpdateArgs, AppRegistryUpdateResult,
    AppRegistryDeleteArgs, AppRegistryDeleteResult,
)
from middlewared.service import GenericCRUDService

from .crud import AppRegistryServicePart


if TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ('AppRegistryService',)


class AppRegistryService(GenericCRUDService[AppRegistryEntry]):

    class Config:
        namespace = 'app.registry'
        cli_namespace = 'app.registry'
        role_prefix = 'APPS'
        entry = AppRegistryEntry
        generic = True
        event_send = False
        event_register = False

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = AppRegistryServicePart(self.context)

    @api_method(AppRegistryCreateArgs, AppRegistryCreateResult, check_annotations=True)
    async def do_create(self, data: AppRegistryCreate) -> AppRegistryEntry:
        """Create an app registry entry."""
        return await self._svc_part.do_create(data)

    @api_method(AppRegistryUpdateArgs, AppRegistryUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: AppRegistryUpdate) -> AppRegistryEntry:
        """Update an app registry entry."""
        return await self._svc_part.do_update(id_, data)

    @api_method(AppRegistryDeleteArgs, AppRegistryDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> None:
        """Delete an app registry entry."""
        await self._svc_part.do_delete(id_)
