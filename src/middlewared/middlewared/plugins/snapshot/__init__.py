from __future__ import annotations

import typing

from middlewared.api import api_method
from middlewared.api.current import (
    PeriodicSnapshotTaskCreateArgs,
    PeriodicSnapshotTaskCreateResult,
    PeriodicSnapshotTaskDeleteArgs,
    PeriodicSnapshotTaskDeleteResult,
    PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs,
    PeriodicSnapshotTaskDeleteWillChangeRetentionForResult,
    PeriodicSnapshotTaskEntry,
    PeriodicSnapshotTaskMaxCountArgs,
    PeriodicSnapshotTaskMaxCountResult,
    PeriodicSnapshotTaskMaxTotalCountArgs,
    PeriodicSnapshotTaskMaxTotalCountResult,
    PeriodicSnapshotTaskRunArgs,
    PeriodicSnapshotTaskRunResult,
    PeriodicSnapshotTaskUpdateArgs,
    PeriodicSnapshotTaskUpdateResult,
    PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs,
    PeriodicSnapshotTaskUpdateWillChangeRetentionForResult,
    PoolSnapshotTaskCreate,
    PoolSnapshotTaskDeleteOptions,
    PoolSnapshotTaskUpdate,
    PoolSnapshotTaskUpdateWillChangeRetentionFor,
)
from middlewared.job import Job
from middlewared.service import GenericCRUDService, job, private
from middlewared.utils.types import AuditCallback

from .attachment import register as register_attachment
from .crud import PeriodicSnapshotTaskServicePart
from .retention import (
    delete_will_change_retention_for,
    fixate_removal_date,
    removal_date_property,
    update_will_change_retention_for,
)
from .task import max_count as _max_count
from .task import max_total_count as _max_total_count
from .task import run as _run

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class PeriodicSnapshotTaskService(GenericCRUDService[PeriodicSnapshotTaskEntry]):

    class Config:
        namespace = "pool.snapshottask"
        cli_namespace = "task.snapshot"
        entry = PeriodicSnapshotTaskEntry
        role_prefix = "SNAPSHOT_TASK"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = PeriodicSnapshotTaskServicePart(self.context)

    @api_method(
        PeriodicSnapshotTaskCreateArgs,
        PeriodicSnapshotTaskCreateResult,
        audit="Snapshot task create:",
        audit_extended=lambda data: data["dataset"],
        check_annotations=True,
    )
    async def do_create(self, data: PoolSnapshotTaskCreate) -> PeriodicSnapshotTaskEntry:
        """
        Create a Periodic Snapshot Task

        Create a Periodic Snapshot Task that will take snapshots of specified `dataset` at specified `schedule`.
        Recursive snapshots can be created if `recursive` flag is enabled. You can `exclude` specific child datasets
        or zvols from the snapshot.

        Snapshots will be automatically destroyed after a certain amount of time, specified by
        `lifetime_value` and `lifetime_unit`.

        If multiple periodic tasks create snapshots at the same time (for example hourly and daily at 00:00)
        the snapshot will be kept until the last of these tasks reaches its expiry time.

        Snapshots will be named according to `naming_schema` which is a `strftime`-like template for snapshot name
        and must contain `%Y`, `%m`, `%d`, `%H` and `%M`.
        """
        return await self._svc_part.do_create(data)

    @api_method(
        PeriodicSnapshotTaskUpdateArgs,
        PeriodicSnapshotTaskUpdateResult,
        audit="Snapshot task update:",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        audit_callback: AuditCallback,
        id_: int,
        data: PoolSnapshotTaskUpdate,
    ) -> PeriodicSnapshotTaskEntry:
        """
        Update a Periodic Snapshot Task with specific `id`.
        """
        return await self._svc_part.do_update(audit_callback, id_, data)

    @api_method(
        PeriodicSnapshotTaskDeleteArgs,
        PeriodicSnapshotTaskDeleteResult,
        audit="Snapshot task delete:",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(
        self,
        audit_callback: AuditCallback,
        id_: int,
        options: PoolSnapshotTaskDeleteOptions,
    ) -> typing.Literal[True]:
        """
        Delete a Periodic Snapshot Task with specific `id`.
        """
        await self._svc_part.do_delete(audit_callback, id_, options)
        return True

    @api_method(
        PeriodicSnapshotTaskMaxCountArgs,
        PeriodicSnapshotTaskMaxCountResult,
        roles=["SNAPSHOT_TASK_READ"],
        check_annotations=True,
    )
    def max_count(self) -> int:
        """
        Returns a maximum amount of snapshots (per-dataset) the system can sustain.
        """
        return _max_count()

    @api_method(
        PeriodicSnapshotTaskMaxTotalCountArgs,
        PeriodicSnapshotTaskMaxTotalCountResult,
        roles=["SNAPSHOT_TASK_READ"],
        check_annotations=True,
    )
    def max_total_count(self) -> int:
        """
        Returns a maximum amount of snapshots (total) the system can sustain.
        """
        return _max_total_count()

    @api_method(
        PeriodicSnapshotTaskRunArgs,
        PeriodicSnapshotTaskRunResult,
        roles=["SNAPSHOT_TASK_WRITE"],
        check_annotations=True,
    )
    @job()
    async def run(self, job: Job, id_: int) -> None:
        """
        Execute a Periodic Snapshot Task of `id`.
        """
        await _run(self.context, id_)

    @private
    async def removal_date_property(self) -> str:
        return await removal_date_property(self.context)

    @private
    @job(
        lock=lambda args: "pool.snapshottask.fixate_removal_date:" + (list(args[0].keys()) + ["-"])[0].split("/")[0],
    )
    async def fixate_removal_date(
        self, job: typing.Any, datasets: dict[str, list[str]], task: PeriodicSnapshotTaskEntry,
    ) -> None:
        await fixate_removal_date(self.context, datasets, task)

    @api_method(
        PeriodicSnapshotTaskUpdateWillChangeRetentionForArgs,
        PeriodicSnapshotTaskUpdateWillChangeRetentionForResult,
        roles=["SNAPSHOT_TASK_READ"],
        check_annotations=True,
    )
    async def update_will_change_retention_for(
        self,
        id_: int,
        data: PoolSnapshotTaskUpdateWillChangeRetentionFor,
    ) -> dict[str, list[str]]:
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is updated
        with `data`.
        """
        return await update_will_change_retention_for(self.context, id_, data)

    @api_method(
        PeriodicSnapshotTaskDeleteWillChangeRetentionForArgs,
        PeriodicSnapshotTaskDeleteWillChangeRetentionForResult,
        roles=["SNAPSHOT_TASK_READ"],
        check_annotations=True,
    )
    async def delete_will_change_retention_for(self, id_: int) -> dict[str, list[str]]:
        """
        Returns a list of snapshots which will change the retention if periodic snapshot task `id` is deleted.
        """
        return await delete_will_change_retention_for(self.context, id_)


async def on_zettarepl_state_changed(middleware: Middleware, id_: str, fields: dict[str, typing.Any]) -> None:
    if id_.startswith("periodic_snapshot_task_"):
        task_id = int(id_.split("_")[-1])
        middleware.send_event("pool.snapshottask.query", "CHANGED", id=task_id, fields={"state": fields})


async def setup(middleware: Middleware) -> None:
    await register_attachment(middleware)
    middleware.register_hook("zettarepl.state_change", on_zettarepl_state_changed)
