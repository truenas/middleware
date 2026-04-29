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


__all__ = ("InitShutdownScriptService",)


class InitShutdownScriptService(GenericCRUDService[InitShutdownScriptEntry]):

    class Config:
        cli_namespace = "system.init_shutdown_script"
        entry = InitShutdownScriptEntry
        generic = True
        role_prefix = "SYSTEM_CRON"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = InitShutdownScriptServicePart(self.context)

    @api_method(InitShutdownScriptCreateArgs, InitShutdownScriptCreateResult, check_annotations=True)
    async def do_create(self, data: InitShutdownScriptCreate) -> InitShutdownScriptEntry:
        """
        Create an initshutdown script task.

        `type` indicates if a command or script should be executed at `when`.

        There are three choices for `when`:

        1) PREINIT - This is early in the boot process before all the services have started
        2) POSTINIT - This is late in the boot process when most of the services have started
        3) SHUTDOWN - This is on shutdown

        `timeout` is an integer value which indicates time in seconds which the system should wait for the execution
        of script/command. It should be noted that a hard limit for a timeout is configured by the base OS, so when
        a script/command is set to execute on SHUTDOWN, the hard limit configured by the base OS is changed adding
        the timeout specified by script/command so it can be ensured that it executes as desired and is not interrupted
        by the base OS's limit.
        """
        return await self._svc_part.do_create(data)

    @api_method(InitShutdownScriptUpdateArgs, InitShutdownScriptUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: InitShutdownScriptUpdate) -> InitShutdownScriptEntry:
        """Update initshutdown script task of `id`."""
        return await self._svc_part.do_update(id_, data)

    @api_method(InitShutdownScriptDeleteArgs, InitShutdownScriptDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """Delete init/shutdown task of `id`."""
        await self._svc_part.do_delete(id_)
        return True

    @private
    @job()
    async def execute_init_tasks(self, job: Job, when: WHEN_ARG) -> None:
        return await execute_init_tasks(self.context, job, when)
