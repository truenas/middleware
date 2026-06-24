from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.api import api_method
from middlewared.api.current import (
    RsyncTaskCreate,
    RsyncTaskCreateArgs,
    RsyncTaskCreateResult,
    RsyncTaskDeleteArgs,
    RsyncTaskDeleteResult,
    RsyncTaskEntry,
    RsyncTaskRunArgs,
    RsyncTaskRunResult,
    RsyncTaskUpdate,
    RsyncTaskUpdateArgs,
    RsyncTaskUpdateResult,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.service import GenericTaskPathService, job
from middlewared.utils.service.task_state import TaskStateMixin

from .crud import RsyncTaskServicePart
from .task import execute_rsync_task

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ("RsyncTaskService",)


class RsyncTaskService(GenericTaskPathService[RsyncTaskEntry], TaskStateMixin):
    _svc_part: RsyncTaskServicePart

    share_task_type = "Rsync"
    task_state_methods = ["rsynctask.run"]

    class Config:
        cli_namespace = "task.rsync"
        entry = RsyncTaskEntry
        generic = True
        role_prefix = "SNAPSHOT_TASK"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = RsyncTaskServicePart(self.context)

    @api_method(RsyncTaskCreateArgs, RsyncTaskCreateResult, check_annotations=True)
    async def do_create(self, data: RsyncTaskCreate) -> RsyncTaskEntry:
        """Create a Rsync Task."""
        return await self._svc_part.do_create(data)

    @api_method(RsyncTaskUpdateArgs, RsyncTaskUpdateResult, check_annotations=True)
    async def do_update(self, id_: int, data: RsyncTaskUpdate) -> RsyncTaskEntry:
        """Update Rsync Task of ``id``."""
        return await self._svc_part.do_update(id_, data)

    @api_method(RsyncTaskDeleteArgs, RsyncTaskDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> bool:
        """Delete Rsync Task of ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @api_method(RsyncTaskRunArgs, RsyncTaskRunResult, roles=["SNAPSHOT_TASK_WRITE"], check_annotations=True)
    @job(lock=lambda args: args[-1], lock_queue_size=1, logs=True)
    def run(self, job: Job, id_: int) -> None:
        """Job to run rsync task of ``id``. Output is saved to the job log excerpt (not syslog)."""
        return execute_rsync_task(self.context, job, id_)

    def _task_state_datastore(self) -> str:
        return self._svc_part._datastore

    def _task_state_datastore_prefix(self) -> str:
        return self._svc_part._datastore_prefix


class RsyncFSAttachmentDelegate(LockableFSAttachmentDelegate[RsyncTaskEntry]):
    name = "rsync"
    title = "Rsync Task"
    service_class = RsyncTaskService
    resource_name = "path"

    async def restart_reload_services(self, attachments: list[RsyncTaskEntry]) -> None:
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call("pool.dataset.register_attachment_delegate", RsyncFSAttachmentDelegate(middleware))
    await middleware.call("network.general.register_activity", "rsync", "Rsync")
    await middleware.call("rsynctask.persist_task_state_on_job_complete")
