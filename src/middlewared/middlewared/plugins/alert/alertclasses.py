from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AlertClassesEntry,
    AlertClassesUpdate,
    AlertClassesUpdateArgs,
    AlertClassesUpdateResult,
)
from middlewared.service import GenericConfigService

from .alertclasses_config import AlertClassesConfigServicePart

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


__all__ = ("AlertClassesService",)


class AlertClassesService(GenericConfigService[AlertClassesEntry]):
    class Config:
        datastore = "system.alertclasses"
        cli_namespace = "system.alert.class"
        entry = AlertClassesEntry
        role_prefix = "ALERT"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = AlertClassesConfigServicePart(self.context)

    @api_method(AlertClassesUpdateArgs, AlertClassesUpdateResult, check_annotations=True)
    async def do_update(self, data: AlertClassesUpdate) -> AlertClassesEntry:
        """
        Update default Alert settings.
        """
        return await self._svc_part.do_update(data)
