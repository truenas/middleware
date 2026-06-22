from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    InitShutdownScriptCreate,
    InitShutdownScriptCreateArgs,
    InitShutdownScriptCreateResult,
    InitShutdownScriptDeleteArgs,
    InitShutdownScriptDeleteResult,
    InitShutdownScriptEntry,
    InitShutdownScriptUpdate,
    InitShutdownScriptUpdateArgs,
    InitShutdownScriptUpdateResult,
)
from middlewared.service import GenericCRUDService, job, private

from .crud import InitShutdownScriptServicePart
from .task import WHEN_ARG, execute_init_tasks

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('InitShutdownScriptService',)


class InitShutdownScriptService(GenericCRUDService[InitShutdownScriptEntry]):

    class Config:
        cli_namespace = 'system.init_shutdown_script'
        entry = InitShutdownScriptEntry
        generic = True
        role_prefix = 'SYSTEM_CRON'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = InitShutdownScriptServicePart(self.context)

    @api_method(InitShutdownScriptCreateArgs, InitShutdownScriptCreateResult, check_annotations=True)
    async def do_create(self, data: InitShutdownScriptCreate) -> InitShutdownScriptEntry:
        """
        Create an initshutdown script task.

        .. note::

            When a script or command is scheduled to run on ``SHUTDOWN``, its ``timeout`` is added to the hard
            shutdown limit imposed by the base OS so that it can run to completion without being interrupted.
        """
        return await self._svc_part.do_create(data)

    @api_method(InitShutdownScriptUpdateArgs, InitShutdownScriptUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: InitShutdownScriptUpdate) -> InitShutdownScriptEntry:
        """Update initshutdown script task of ``id``."""
        return await self._svc_part.do_update(id_, data)

    @api_method(InitShutdownScriptDeleteArgs, InitShutdownScriptDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """Delete init/shutdown task of ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @private
    @job()
    async def execute_init_tasks(self, job: Job, when: WHEN_ARG) -> None:
        return await execute_init_tasks(self.context, job, when)
