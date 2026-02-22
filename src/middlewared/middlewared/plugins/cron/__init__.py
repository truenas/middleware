from __future__ import annotations

from typing import Any, Literal, TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    CronJobEntry, CronJobSchedule, QueryOptions,
    CronJobCreateArgs, CronJobCreateResult, CronJobCreate,
    CronJobUpdateArgs, CronJobUpdateResult, CronJobUpdate,
    CronJobDeleteArgs, CronJobDeleteResult,
    CronJobRunArgs, CronJobRunResult,
)
from middlewared.service import CRUDService, job, private

from .crud import CronJobServicePart
from .execute import construct_cron_command as _construct_cron_command, execute_cron_task


if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ('CronJobService',)


class CronJobService(CRUDService[CronJobEntry]):

    class Config:
        cli_namespace = 'task.cron_job'
        entry = CronJobEntry
        generic = True
        role_prefix = 'SYSTEM_CRON'

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = CronJobServicePart(self.context)

    async def query(
        self, filters: list[Any] | None = None, options: dict[str, Any] | None = None
    ) -> list[CronJobEntry] | CronJobEntry | int:
        return await self._svc_part.query(filters or [], QueryOptions(**(options or {})))

    async def get_instance(self, id_: int, options: dict[str, Any] | None = None) -> CronJobEntry:
        return await self._svc_part.get_instance(id_, extra=(options or {}).get('extra'))

    @api_method(CronJobCreateArgs, CronJobCreateResult, check_annotations=True)
    async def do_create(self, data: CronJobCreate) -> CronJobEntry:
        """
        Create a new cron job.

        `stderr` and `stdout` are boolean values which if `true`, represent that we would like to suppress
        standard error / standard output respectively.
        """
        return await self._svc_part.do_create(data)

    @api_method(CronJobUpdateArgs, CronJobUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: CronJobUpdate) -> CronJobEntry:
        """
        Update cronjob of `id`.
        """
        return await self._svc_part.do_update(id_, data)

    @api_method(CronJobDeleteArgs, CronJobDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """
        Delete cronjob of `id`.
        """
        await self._svc_part.do_delete(id_)
        return True

    @api_method(CronJobRunArgs, CronJobRunResult, roles=['SYSTEM_CRON_WRITE'], check_annotations=True)
    @job(lock=lambda args: f'cron_job_run_{args[0]}', logs=True, lock_queue_size=1)
    def run(self, job: Job, id_: int, skip_disabled: bool) -> None:
        """
        Job to run cronjob task of `id`.
        """
        return execute_cron_task(self.context, job, id_, skip_disabled)

    @private
    async def construct_cron_command(
        self, schedule: dict[str, str] | CronJobSchedule, user: str, command: str,
        stdout: bool = True, stderr: bool = True
    ) -> list[str]:
        if not isinstance(schedule, CronJobSchedule):
            schedule = CronJobSchedule(**schedule)
        return _construct_cron_command(schedule, user, command, stdout, stderr)
