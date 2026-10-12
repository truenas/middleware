from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from middlewared.api.current import (
    PeriodicSnapshotTaskEntry,
    ReplicationCountEligibleManualSnapshotsArgs,
    ReplicationEligibleManualSnapshots,
)
from middlewared.service import Service, private
from middlewared.utils.service.task_state import TaskStateMixin

from . import datasets as _datasets
from . import run as _run
from . import snapshot_create as _snapshot_create
from .removal_date import ZettareplRemovalDatePart
from .runtime import ZettareplRuntimePart
from .state import ZettareplStatePart
from .transport import Transport

if TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ("ZettareplService",)


class ZettareplService(Service, TaskStateMixin):
    task_state_methods = ["replication.run"]

    class Config:
        private = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)

        self._removal_date = ZettareplRemovalDatePart(self.context)
        self._runtime = ZettareplRuntimePart(self.context)
        self._state = ZettareplStatePart(self.context)

    @private
    async def is_running(self) -> bool:
        return await self._runtime.is_running()

    @private
    def start(self) -> None:
        self._runtime.start()

    @private
    def get_definition(self) -> dict[str, Any]:
        return self._runtime.get_definition()

    @private
    async def build_definition(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return await self._runtime.build_definition()

    @private
    def update_config(self, config: dict[str, Any]) -> None:
        self._runtime.update_tasks()

    @private
    def update_tasks(self) -> None:
        self._runtime.update_tasks()

    @private
    async def notify_definition_read(self, data: dict[str, Any]) -> None:
        await self._runtime.notify_definition_read(data)

    @private
    def notify_status(self, data: dict[str, Any]) -> None:
        self._runtime.notify_status(data)

    @private
    def notify(self, notifications: list[dict[str, Any]]) -> None:
        self._runtime.notify(notifications)

    @private
    async def periodic_snapshot_task_start(self, task_id: str) -> dict[str, Any]:
        return await self._runtime.periodic_snapshot_task_start(task_id)

    @private
    async def periodic_snapshot_task_end(self, task_id: str) -> None:
        await self._runtime.periodic_snapshot_task_end(task_id)

    @private
    def run_periodic_snapshot_task(self, id_: int) -> None:
        _run.run_periodic_snapshot_task(self._runtime, id_)

    @private
    def run_replication_task(self, id_: int, really_run: bool, job: Job) -> None:
        _run.run_replication_task(self._runtime, id_, really_run, job)

    @private
    def run_onetime_replication_task(self, job: Job, task: dict[str, Any]) -> None:
        _run.run_onetime_replication_task(self._runtime, job, task)

    @private
    async def list_datasets(self, transport: Transport, ssh_credentials: int | None = None) -> list[str]:
        return await _datasets.list_datasets(self.context, transport, ssh_credentials)

    @private
    async def create_dataset(
        self,
        dataset: str,
        transport: Transport,
        ssh_credentials: int | None = None,
    ) -> None:
        await _datasets.create_dataset(self.context, dataset, transport, ssh_credentials)

    @private
    async def count_eligible_manual_snapshots(
        self,
        data: ReplicationCountEligibleManualSnapshotsArgs,
    ) -> ReplicationEligibleManualSnapshots:
        return await _datasets.count_eligible_manual_snapshots(self.context, data)

    @private
    async def get_source_target_datasets_mapping(
        self,
        source_datasets: list[str],
        target_dataset: str,
    ) -> dict[str, str]:
        return _datasets.get_source_target_datasets_mapping(source_datasets, target_dataset)

    @private
    async def reverse_source_target_datasets(
        self,
        source_datasets: list[str],
        target_dataset: str,
    ) -> tuple[list[str], str]:
        return _datasets.reverse_source_target_datasets(source_datasets, target_dataset)

    @private
    async def target_unmatched_snapshots(
        self,
        direction: Literal["PUSH", "PULL"],
        source_datasets: list[str],
        target_dataset: str,
        transport: Transport,
        ssh_credentials: int | None = None,
    ) -> dict[str, list[str]]:
        return await _datasets.target_unmatched_snapshots(
            self.context, direction, source_datasets, target_dataset, transport, ssh_credentials
        )

    @private
    def create_recursive_snapshot_with_exclude(self, dataset: str, snapshot: str, exclude: list[str]) -> None:
        _snapshot_create.create_recursive_snapshot_with_exclude(dataset, snapshot, exclude)

    @private
    def get_state(self) -> dict[str, Any]:
        return self._state.get_state()

    @private
    def get_state_internal(self, task_id: str) -> dict[str, Any] | None:
        return self._state.get_state_internal(task_id)

    @private
    def get_internal_task_state(self, task_id: str) -> dict[str, Any]:
        return self._state.get_internal_task_state(task_id)

    @private
    def set_error(self, error: dict[str, Any] | None) -> None:
        self._state.set_error(error)

    @private
    def set_definition_errors(self, definition_errors: dict[str, Any]) -> None:
        self._state.set_definition_errors(definition_errors)

    @private
    def notify_definition(self, definition: dict[str, Any], hold_tasks: dict[str, Any]) -> None:
        self._state.notify_definition(definition, hold_tasks)

    @private
    def set_state(self, task_id: str, state: dict[str, Any]) -> None:
        self._state.set_state(task_id, state)

    @private
    def set_last_snapshot(self, task_id: str, last_snapshot: str) -> None:
        self._state.set_last_snapshot(task_id, last_snapshot)

    @private
    def remove_task(self, task_id: str) -> None:
        self._state.remove_task(task_id)

    @private
    async def load_state(self) -> None:
        await self._state.load_state()

    @private
    async def flush_state(self) -> None:
        await self._state.flush_state()

    @private
    def load_removal_dates(self, pool: str | None = None) -> None:
        self._removal_date.load_removal_dates(pool)

    @private
    def get_removal_dates(self) -> dict[str, datetime] | None:
        return self._removal_date.get_removal_dates()

    @private
    def periodic_snapshot_task_snapshots(self, task: PeriodicSnapshotTaskEntry) -> set[str]:
        return self._removal_date.periodic_snapshot_task_snapshots(task)

    @private
    def fixate_removal_date(self, datasets: dict[str, list[str]], task: PeriodicSnapshotTaskEntry) -> None:
        self._removal_date.fixate_removal_date(datasets, task)

    @private
    def annotate_snapshots(self, snapshots: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return self._removal_date.annotate_snapshots(snapshots)

    async def terminate(self) -> None:
        await self._runtime.terminate()


async def pool_configuration_change(middleware: Middleware, *args: Any, **kwargs: Any) -> None:
    await middleware.call2(middleware.services.zettarepl.update_tasks)


async def setup(middleware: Middleware) -> None:
    middleware.event_register("zettarepl.command", "Sent to the zettarepl service to control it.", private=True)

    await middleware.call2(middleware.services.zettarepl.load_state)

    try:
        await middleware.call2(middleware.services.zettarepl.start)
    except Exception:
        middleware.logger.error("Unhandled exception during zettarepl startup", exc_info=True)

    middleware.register_hook("pool.post_import", pool_configuration_change, sync=True)
    middleware.register_hook("pool.post_export", pool_configuration_change, sync=True)

    middleware.register_hook("pool.post_lock", pool_configuration_change, sync=True)
    middleware.register_hook("pool.post_unlock", pool_configuration_change, sync=True)

    middleware.register_hook("pool.post_create_or_update", pool_configuration_change, sync=True)
