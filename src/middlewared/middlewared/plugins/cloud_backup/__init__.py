from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    CloudBackupAbortArgs,
    CloudBackupAbortResult,
    CloudBackupCreate,
    CloudBackupCreateArgs,
    CloudBackupCreateResult,
    CloudBackupDeleteArgs,
    CloudBackupDeleteResult,
    CloudBackupDeleteSnapshotArgs,
    CloudBackupDeleteSnapshotResult,
    CloudBackupEntry,
    CloudBackupListSnapshotDirectoryArgs,
    CloudBackupListSnapshotDirectoryResult,
    CloudBackupListSnapshotsArgs,
    CloudBackupListSnapshotsResult,
    CloudBackupRestoreArgs,
    CloudBackupRestoreOptions,
    CloudBackupRestoreResult,
    CloudBackupSnapshot,
    CloudBackupSnapshotItem,
    CloudBackupSyncArgs,
    CloudBackupSyncOptions,
    CloudBackupSyncResult,
    CloudBackupTransferSettingChoicesArgs,
    CloudBackupTransferSettingChoicesResult,
    CloudBackupUpdate,
    CloudBackupUpdateArgs,
    CloudBackupUpdateResult,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.service import GenericTaskPathService, job, private
from middlewared.utils.service.task_state import TaskStateMixin

from .crud import CloudBackupServicePart
from .init import ensure_initialized as ensure_initialized_impl
from .restore import do_restore
from .snapshot import delete_snapshot as delete_snapshot_impl
from .snapshot import list_snapshot_directory as list_snapshot_directory_impl
from .snapshot import list_snapshots as list_snapshots_impl
from .sync import TRANSFER_SETTING_ARGS, do_abort, do_sync

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ("CloudBackupService",)


class CloudBackupService(GenericTaskPathService[CloudBackupEntry], TaskStateMixin):
    _svc_part: CloudBackupServicePart

    share_task_type = "CloudBackup"
    task_state_methods = ["cloud_backup.sync", "cloud_backup.restore"]

    class Config:
        namespace = "cloud_backup"
        cli_namespace = "task.cloud_backup"
        entry = CloudBackupEntry
        generic = True
        role_prefix = "CLOUD_BACKUP"

    def __init__(self, middleware: Middleware) -> None:
        super().__init__(middleware)
        self._svc_part = CloudBackupServicePart(self.context)

    @api_method(CloudBackupCreateArgs, CloudBackupCreateResult, pass_app=True, check_annotations=True)
    async def do_create(self, app: App, data: CloudBackupCreate) -> CloudBackupEntry:
        """Create a new cloud backup task."""
        return await self._svc_part.do_create(app, data)

    @api_method(CloudBackupUpdateArgs, CloudBackupUpdateResult, pass_app=True, check_annotations=True)
    async def do_update(self, app: App, id_: int, data: CloudBackupUpdate) -> CloudBackupEntry:
        """Update the cloud backup entry `id` with `data`."""
        return await self._svc_part.do_update(app, id_, data)

    @api_method(CloudBackupDeleteArgs, CloudBackupDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """Delete cloud backup entry `id`."""
        await self._svc_part.do_delete(id_)
        return True

    @api_method(
        CloudBackupTransferSettingChoicesArgs, CloudBackupTransferSettingChoicesResult, check_annotations=True,
    )
    async def transfer_setting_choices(self) -> list[Literal["DEFAULT", "PERFORMANCE", "FAST_STORAGE"]]:
        """Return all possible choices for `cloud_backup.create.transfer_setting`."""
        return list(TRANSFER_SETTING_ARGS)

    @api_method(CloudBackupSyncArgs, CloudBackupSyncResult, roles=["CLOUD_BACKUP_WRITE"], check_annotations=True)
    @job(lock=lambda args: "cloud_backup:{}".format(args[-1]), lock_queue_size=1, logs=True, abortable=True)
    def sync(self, job: Job, id_: int, options: CloudBackupSyncOptions) -> None:
        """Run the cloud backup job `id`."""
        return do_sync(self.context, job, id_, options)

    @api_method(CloudBackupAbortArgs, CloudBackupAbortResult, roles=["CLOUD_BACKUP_WRITE"], check_annotations=True)
    def abort(self, id_: int) -> bool:
        """Abort a running cloud backup task."""
        return do_abort(self.context, id_)

    @api_method(
        CloudBackupRestoreArgs, CloudBackupRestoreResult, roles=["FILESYSTEM_DATA_WRITE"], check_annotations=True,
    )
    @job(logs=True)
    def restore(
        self,
        job: Job,
        id_: int,
        snapshot_id: str,
        subfolder: str,
        destination_path: str,
        options: CloudBackupRestoreOptions,
    ) -> None:
        """
        Restore files to the directory `destination_path` from the `snapshot_id` subfolder `subfolder`
        created by the cloud backup job `id`.
        """
        return do_restore(self.context, job, id_, snapshot_id, subfolder, destination_path, options)

    @api_method(
        CloudBackupListSnapshotsArgs, CloudBackupListSnapshotsResult, roles=["CLOUD_BACKUP_READ"],
        check_annotations=True,
    )
    def list_snapshots(self, id_: int) -> list[CloudBackupSnapshot]:
        """List existing snapshots for the cloud backup job `id`."""
        return list_snapshots_impl(self.context, id_)

    @api_method(
        CloudBackupListSnapshotDirectoryArgs, CloudBackupListSnapshotDirectoryResult, roles=["CLOUD_BACKUP_READ"],
        check_annotations=True,
    )
    def list_snapshot_directory(self, id_: int, snapshot_id: str, path: str) -> list[CloudBackupSnapshotItem]:
        """List files in the directory `path` of the `snapshot_id` created by the cloud backup job `id`."""
        return list_snapshot_directory_impl(self.context, id_, snapshot_id, path)

    @api_method(
        CloudBackupDeleteSnapshotArgs, CloudBackupDeleteSnapshotResult, roles=["CLOUD_BACKUP_WRITE"],
        check_annotations=True,
    )
    @job(lock=lambda args: "cloud_backup:{}".format(args[-1]), lock_queue_size=1)
    def delete_snapshot(self, job: Job, id_: int, snapshot_id: str) -> None:
        """Delete snapshot `snapshot_id` created by the cloud backup job `id`."""
        return delete_snapshot_impl(self.context, job, id_, snapshot_id)

    @private
    def ensure_initialized(self, cloud_backup: CloudBackupEntry | CloudBackupCreate) -> None:
        ensure_initialized_impl(self.context, cloud_backup)

    @private
    def validate_zvol(self, path: str) -> None:
        self._svc_part.validate_zvol(path)

    def _task_state_datastore(self) -> str:
        return self._svc_part._datastore

    def _task_state_datastore_prefix(self) -> str:
        return self._svc_part._datastore_prefix


class CloudBackupFSAttachmentDelegate(LockableFSAttachmentDelegate[CloudBackupEntry]):
    name = "cloud_backup"
    title = "Cloud Backup Task"
    service_class = CloudBackupService
    resource_name = "path"

    async def restart_reload_services(self, attachments: list[CloudBackupEntry]) -> None:
        await (await self.middleware.call("service.control", "RESTART", "cron")).wait(raise_error=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call("pool.dataset.register_attachment_delegate", CloudBackupFSAttachmentDelegate(middleware))
    await middleware.call("network.general.register_activity", "cloud_backup", "Cloud backup")
    await middleware.call2(middleware.services.cloud_backup.persist_task_state_on_job_complete)
