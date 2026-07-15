from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    ReplicationCountEligibleManualSnapshotsArgs,
    ReplicationCountEligibleManualSnapshotsResult,
    ReplicationCreate,
    ReplicationCreateArgs,
    ReplicationCreateDatasetArgs,
    ReplicationCreateDatasetResult,
    ReplicationCreateResult,
    ReplicationDeleteArgs,
    ReplicationDeleteResult,
    ReplicationEntry,
    ReplicationListDatasetsArgs,
    ReplicationListDatasetsResult,
    ReplicationListNamingSchemasArgs,
    ReplicationListNamingSchemasResult,
    ReplicationRestoreArgs,
    ReplicationRestoreOptions,
    ReplicationRestoreResult,
    ReplicationRunArgs,
    ReplicationRunOnetimeArgs,
    ReplicationRunOnetimeResult,
    ReplicationRunResult,
    ReplicationTargetUnmatchedSnapshotsArgs,
    ReplicationTargetUnmatchedSnapshotsResult,
    ReplicationUpdate,
    ReplicationUpdateArgs,
    ReplicationUpdateResult,
)
from middlewared.service import GenericCRUDService, job, private
from middlewared.utils.types import AuditCallback

from . import methods as _methods
from .crud import ReplicationServicePart
from .methods import ReplicationPairArgs, ReplicationPairData, ReplicationPairResult

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware

__all__ = ("ReplicationService",)


class ReplicationService(GenericCRUDService[ReplicationEntry]):
    _svc_part: ReplicationServicePart

    class Config:
        datastore = "storage.replication"
        datastore_prefix = "repl_"
        cli_namespace = "task.replication"
        entry = ReplicationEntry
        role_prefix = "REPLICATION_TASK"
        generic = True

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = ReplicationServicePart(self.context)

    @api_method(
        ReplicationCreateArgs,
        ReplicationCreateResult,
        audit="Replication task create:",
        audit_extended=lambda data: data["name"],
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    async def do_create(self, app: App, data: ReplicationCreate) -> ReplicationEntry:
        """
        Create a Replication Task that will push or pull ZFS snapshots to or from remote host.
        """
        return await self._svc_part.do_create(app, data)

    @api_method(
        ReplicationUpdateArgs,
        ReplicationUpdateResult,
        audit="Replication task update:",
        audit_callback=True,
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    async def do_update(
        self,
        app: App,
        audit_callback: AuditCallback,
        id_: int,
        data: ReplicationUpdate,
    ) -> ReplicationEntry:
        """
        Update a Replication Task with specific ``id``.
        """
        return await self._svc_part.do_update(app, audit_callback, id_, data)

    @api_method(
        ReplicationDeleteArgs,
        ReplicationDeleteResult,
        audit="Replication task delete:",
        audit_callback=True,
        check_annotations=True,
    )
    async def do_delete(self, audit_callback: AuditCallback, id_: int) -> bool:
        """
        Delete a replication task with the given ``id``.
        """
        return await self._svc_part.do_delete(audit_callback, id_)

    @api_method(
        ReplicationRunArgs,
        ReplicationRunResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    @job(logs=True, read_roles=["REPLICATION_TASK_READ"])
    async def run(self, job: Job, id_: int, really_run: bool = True) -> None:
        """
        Run Replication Task of ``id``.
        """
        await _methods.run_task(self.context, job, id_, really_run)

    @api_method(
        ReplicationRunOnetimeArgs,
        ReplicationRunOnetimeResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    @job(logs=True)
    async def run_onetime(self, job: Job, data: ReplicationRunOnetimeArgs) -> None:
        """
        Run replication task without creating it.
        """
        await self._svc_part.run_onetime(job, data)

    @api_method(
        ReplicationListDatasetsArgs,
        ReplicationListDatasetsResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    async def list_datasets(
        self,
        transport: Literal["SSH", "SSH+NETCAT", "LOCAL"],
        ssh_credentials: int | None = None,
    ) -> list[str]:
        """
        List datasets on remote side.
        """
        return await _methods.list_datasets(self.context, transport, ssh_credentials)

    @api_method(
        ReplicationCreateDatasetArgs,
        ReplicationCreateDatasetResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    async def create_dataset(
        self,
        dataset: str,
        transport: Literal["SSH", "SSH+NETCAT", "LOCAL"],
        ssh_credentials: int | None = None,
    ) -> None:
        """
        Creates dataset on remote side.
        """
        return await _methods.create_dataset(self.context, dataset, transport, ssh_credentials)

    @api_method(
        ReplicationListNamingSchemasArgs,
        ReplicationListNamingSchemasResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    async def list_naming_schemas(self) -> list[str]:
        """
        List all naming schemas used in periodic snapshot and replication tasks.
        """
        return await _methods.list_naming_schemas(self.context)

    @api_method(
        ReplicationCountEligibleManualSnapshotsArgs,
        ReplicationCountEligibleManualSnapshotsResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    async def count_eligible_manual_snapshots(
        self,
        data: ReplicationCountEligibleManualSnapshotsArgs,
    ) -> ReplicationCountEligibleManualSnapshotsResult:
        """
        Count how many existing snapshots of ``dataset`` match ``naming_schema``.
        """
        return await _methods.count_eligible_manual_snapshots(self.context, data)

    @api_method(
        ReplicationTargetUnmatchedSnapshotsArgs,
        ReplicationTargetUnmatchedSnapshotsResult,
        roles=["REPLICATION_TASK_WRITE"],
        check_annotations=True,
    )
    async def target_unmatched_snapshots(
        self,
        direction: Literal["PUSH", "PULL"],
        source_datasets: list[str],
        target_dataset: str,
        transport: Literal["SSH", "SSH+NETCAT", "LOCAL"],
        ssh_credentials: int | None = None,
    ) -> dict[str, list[str]]:
        """
        Check if target has any snapshots that do not exist on source. Returns these snapshots grouped by dataset.
        """
        return await _methods.target_unmatched_snapshots(
            self.context,
            direction,
            source_datasets,
            target_dataset,
            transport,
            ssh_credentials,
        )

    @private
    def new_snapshot_name(self, naming_schema: str) -> str:
        return _methods.new_snapshot_name(naming_schema)

    # Legacy pair support
    @api_method(ReplicationPairArgs, ReplicationPairResult, private=True, check_annotations=True)
    async def pair(self, data: ReplicationPairData) -> dict[str, Any]:
        return await _methods.pair(self.context, data)

    @api_method(
        ReplicationRestoreArgs,
        ReplicationRestoreResult,
        roles=["REPLICATION_TASK_WRITE"],
        pass_app=True,
        pass_app_require=True,
        check_annotations=True,
    )
    async def restore(self, app: App, id_: int, data: ReplicationRestoreOptions) -> ReplicationEntry:
        """
        Create the opposite of replication task ``id`` (PULL if it was PUSH and vice versa).
        """
        return await _methods.restore(self.context, app, id_, data)
