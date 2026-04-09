from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    AppEntry,
)
from middlewared.service import GenericCRUDService, job, private

from .crud import AppServicePart


if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('AppService',)


class AppService(GenericCRUDService[AppEntry]):

    class Config:
        namespace = 'app'
        event_send = False
        cli_namespace = 'app'
        role_prefix = 'APPS'
        entry = AppEntry

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = AppServicePart(self.context)
