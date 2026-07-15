from __future__ import annotations

from typing import TYPE_CHECKING, Any, Literal

from middlewared.api import api_method
from middlewared.api.current import (
    CloudSyncAbortArgs,
    CloudSyncAbortResult,
    CloudSyncCreate,
    CloudSyncCreateArgs,
    CloudSyncCreateBucketArgs,
    CloudSyncCreateBucketResult,
    CloudSyncCreateResult,
    CloudSyncDeleteArgs,
    CloudSyncDeleteResult,
    CloudSyncEntry,
    CloudSyncListBucketsArgs,
    CloudSyncListBucketsResult,
    CloudSyncListDirectory,
    CloudSyncListDirectoryArgs,
    CloudSyncListDirectoryResult,
    CloudSyncProvider,
    CloudSyncProvidersArgs,
    CloudSyncProvidersResult,
    CloudSyncRestoreArgs,
    CloudSyncRestoreResult,
    CloudSyncSyncArgs,
    CloudSyncSyncOnetimeArgs,
    CloudSyncSyncOnetimeResult,
    CloudSyncSyncOptions,
    CloudSyncSyncResult,
    CloudSyncUpdate,
    CloudSyncUpdateArgs,
    CloudSyncUpdateResult,
    RestoreOpts,
)
from middlewared.common.attachment import LockableFSAttachmentDelegate
from middlewared.plugins.cloud.remotes import remote_classes
from middlewared.service import GenericTaskPathService, job
from middlewared.utils.service.task_state import TaskStateMixin

from .crud import (
    CloudProviderRemovedAlert,
    CloudSyncModel,
    CloudSyncServicePart,
    CloudSyncTaskFailedAlert,
)
from .directory import create_bucket as create_bucket_impl
from .directory import list_buckets as list_buckets_impl
from .directory import list_directory as list_directory_impl
from .directory import providers as providers_impl
from .lock import FsLockManager
from .rclone import RcloneConfig, RcloneVerboseLogCutter, lsjson_error_excerpt
from .sync import do_abort, do_restore, do_sync, do_sync_onetime

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = (
    "CloudSyncService",
    "CloudSyncModel",
    "CloudSyncServicePart",
    "CloudSyncTaskFailedAlert",
    "CloudProviderRemovedAlert",
    "FsLockManager",
    "RcloneConfig",
    "RcloneVerboseLogCutter",
    "lsjson_error_excerpt",
)


class CloudSyncService(GenericTaskPathService[CloudSyncEntry], TaskStateMixin):
    _svc_part: CloudSyncServicePart

    share_task_type = "CloudSync"
    task_state_methods = ["cloudsync.sync", "cloudsync.restore"]

    class Config:
        namespace = "cloudsync"
        cli_namespace = "task.cloud_sync"
        entry = CloudSyncEntry
        generic = True
        role_prefix = "CLOUD_SYNC"

    def __init__(self, middleware: Middleware) -> None:
        from middlewared.plugins.cloud_credentials import CredentialsService
        super().__init__(middleware)
        self.credentials = CredentialsService(middleware)
        self._svc_part = CloudSyncServicePart(self.context)

    @api_method(CloudSyncCreateArgs, CloudSyncCreateResult, pass_app=True, check_annotations=True)
    async def do_create(self, app: App, data: CloudSyncCreate) -> CloudSyncEntry:
        """
        Creates a new cloud_sync entry.
        """
        return await self._svc_part.do_create(app, data)

    @api_method(CloudSyncUpdateArgs, CloudSyncUpdateResult, pass_app=True, check_annotations=True)
    async def do_update(self, app: App, id_: int, data: CloudSyncUpdate) -> CloudSyncEntry:
        """
        Updates the cloud_sync entry ``id`` with ``data``.
        """
        return await self._svc_part.do_update(app, id_, data)

    @api_method(CloudSyncDeleteArgs, CloudSyncDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """
        Deletes cloud_sync entry ``id``.
        """
        await self._svc_part.do_delete(id_)
        return True

    @api_method(CloudSyncCreateBucketArgs, CloudSyncCreateBucketResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    def create_bucket(self, credentials_id: int, name: str) -> None:
        """
        Creates a new bucket ``name`` using ``credentials_id``.
        """
        create_bucket_impl(self._svc_part, credentials_id, name)

    @api_method(CloudSyncListBucketsArgs, CloudSyncListBucketsResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    def list_buckets(self, credentials_id: int) -> list[dict[str, Any]]:
        """
        List the buckets available to the cloud sync credential identified by ``credentials_id``.

        Use this when configuring a cloud sync task to discover which buckets a set of credentials
        can access. Each returned entry describes a bucket as a directory-like listing.

        Only providers that organize storage into buckets (such as Amazon S3 or Storj) are
        supported. A JSON-RPC ``error`` response (code ``-32001``, *Method call error*) is returned
        when the credential does not exist or its provider does not use buckets.
        """
        return list_buckets_impl(self._svc_part, credentials_id)

    @api_method(CloudSyncListDirectoryArgs, CloudSyncListDirectoryResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    def list_directory(self, cloud_sync_ls: CloudSyncListDirectory) -> list[dict[str, Any]]:
        """
        List contents of a remote bucket / directory.

        If the remote supports buckets, the path is constructed from the ``bucket`` and ``folder`` keys in
        ``attributes``; otherwise it is constructed from the ``folder`` key alone. For example, an S3 path is
        ``bucketname/directory/name`` and a Dropbox path is ``directory/name``.
        """
        return list_directory_impl(self._svc_part, cloud_sync_ls)

    @api_method(CloudSyncSyncArgs, CloudSyncSyncResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    @job(lock=lambda args: "cloud_sync:{}".format(args[-1]), lock_queue_size=1, logs=True, abortable=True,
         read_roles=["CLOUD_SYNC_READ"])
    def sync(self, job: Job, id_: int, options: CloudSyncSyncOptions) -> None:
        """
        Run the cloud_sync job ``id``, syncing the local data to remote.
        """
        do_sync(self.context, job, id_, options)

    @api_method(CloudSyncSyncOnetimeArgs, CloudSyncSyncOnetimeResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    @job(logs=True, abortable=True)
    def sync_onetime(self, job: Job, cloud_sync: CloudSyncCreate, options: CloudSyncSyncOptions) -> None:
        """
        Run cloud sync task without creating it.
        """
        do_sync_onetime(self.context, self._svc_part, job, cloud_sync, options)

    @api_method(CloudSyncAbortArgs, CloudSyncAbortResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    def abort(self, id_: int) -> bool:
        """
        Aborts cloud sync task.
        """
        return do_abort(self.context, id_)

    @api_method(CloudSyncProvidersArgs, CloudSyncProvidersResult, roles=["CLOUD_SYNC_READ"], check_annotations=True)
    def providers(self) -> list[CloudSyncProvider]:
        """
        Returns a list of dictionaries of supported providers for Cloud Sync Tasks.
        """
        return providers_impl(self._svc_part)

    @api_method(CloudSyncRestoreArgs, CloudSyncRestoreResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    def restore(self, id_: int, opts: RestoreOpts) -> CloudSyncEntry:
        """
        Create the opposite of cloud sync task ``id`` (PULL if it was PUSH and vice versa).
        """
        return do_restore(self.context, id_, opts)

    def _task_state_datastore(self) -> str:
        return self._svc_part._datastore

    def _task_state_datastore_prefix(self) -> str:
        return self._svc_part._datastore_prefix


for cls in remote_classes:
    for method_name in cls.extra_methods:
        setattr(CloudSyncService, f"{cls.name.lower()}_{method_name}", getattr(cls, method_name))


class CloudSyncFSAttachmentDelegate(LockableFSAttachmentDelegate[CloudSyncEntry]):
    name = "cloudsync"
    title = "CloudSync Task"
    service_class = CloudSyncService
    resource_name = "path"

    async def restart_reload_services(self, attachments: list[CloudSyncEntry]) -> None:
        await (await self.call2(self.s.service.control, "RESTART", "cron")).wait(raise_error=True)


async def setup(middleware: Middleware) -> None:
    await middleware.call("pool.dataset.register_attachment_delegate", CloudSyncFSAttachmentDelegate(middleware))
    await middleware.call("network.general.register_activity", "cloud_sync", "Cloud sync")
    await middleware.call2(middleware.services.cloudsync.persist_task_state_on_job_complete)
