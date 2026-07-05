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

from .credentials import CredentialsService
from .crud import CloudProviderRemovedAlert, CloudSyncServicePart, CloudSyncTaskFailedAlert

if TYPE_CHECKING:
    from middlewared.api.base.server.app import App
    from middlewared.job import Job
    from middlewared.main import Middleware


__all__ = ("CloudSyncService", "CredentialsService", "CloudProviderRemovedAlert", "CloudSyncTaskFailedAlert")


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
        super().__init__(middleware)
        self.credentials = CredentialsService(middleware)
        self._svc_part = CloudSyncServicePart(self.context)

    @api_method(CloudSyncCreateArgs, CloudSyncCreateResult, pass_app=True, check_annotations=True)
    async def do_create(self, app: App, data: CloudSyncCreate) -> CloudSyncEntry:
        """Create a new cloud sync task."""
        return await self._svc_part.do_create(app, data)

    @api_method(CloudSyncUpdateArgs, CloudSyncUpdateResult, pass_app=True, check_annotations=True)
    async def do_update(self, app: App, id_: int, data: CloudSyncUpdate) -> CloudSyncEntry:
        """Update the cloud sync task ``id`` with ``data``."""
        return await self._svc_part.do_update(app, id_, data)

    @api_method(CloudSyncDeleteArgs, CloudSyncDeleteResult, check_annotations=True)
    async def do_delete(self, id_: int) -> Literal[True]:
        """Delete cloud sync task ``id``."""
        await self._svc_part.do_delete(id_)
        return True

    @api_method(CloudSyncCreateBucketArgs, CloudSyncCreateBucketResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    def create_bucket(self, credentials_id: int, name: str) -> None:
        """Create a new bucket ``name`` using ``credentials_id``."""
        return self._svc_part.create_bucket(credentials_id, name)

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
        return self._svc_part.list_buckets(credentials_id)

    @api_method(CloudSyncListDirectoryArgs, CloudSyncListDirectoryResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    def list_directory(self, data: CloudSyncListDirectory) -> list[dict[str, Any]]:
        """
        List contents of a remote bucket / directory.

        If the remote supports buckets, the path is constructed from the ``bucket`` and ``folder`` keys in
        ``attributes``; otherwise it is constructed from the ``folder`` key alone. For example, an S3 path is
        ``bucketname/directory/name`` and a Dropbox path is ``directory/name``.
        """
        return self._svc_part.list_directory(data)

    @api_method(CloudSyncSyncArgs, CloudSyncSyncResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    @job(lock=lambda args: "cloud_sync:{}".format(args[-1]), lock_queue_size=1, logs=True, abortable=True,
         read_roles=["CLOUD_SYNC_READ"])
    def sync(self, job: Job, id_: int, options: CloudSyncSyncOptions) -> None:
        """Run the cloud sync job ``id``, syncing the local data to remote."""
        return self._svc_part.sync(job, id_, options)

    @api_method(CloudSyncSyncOnetimeArgs, CloudSyncSyncOnetimeResult, roles=["CLOUD_SYNC_WRITE"],
                check_annotations=True)
    @job(logs=True, abortable=True)
    def sync_onetime(self, job: Job, data: CloudSyncCreate, options: CloudSyncSyncOptions) -> None:
        """Run cloud sync task without creating it."""
        return self._svc_part.sync_onetime(job, data, options)

    @api_method(CloudSyncAbortArgs, CloudSyncAbortResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    def abort(self, id_: int) -> bool:
        """Abort a running cloud sync task."""
        return self._svc_part.abort(id_)

    @api_method(CloudSyncProvidersArgs, CloudSyncProvidersResult, roles=["CLOUD_SYNC_READ"], check_annotations=True)
    def providers(self) -> list[CloudSyncProvider]:
        """Return a list of supported providers for Cloud Sync Tasks."""
        return self._svc_part.providers()

    @api_method(CloudSyncRestoreArgs, CloudSyncRestoreResult, roles=["CLOUD_SYNC_WRITE"], check_annotations=True)
    def restore(self, id_: int, opts: RestoreOpts) -> CloudSyncEntry:
        """Create the opposite of cloud sync task ``id`` (PULL if it was PUSH and vice versa)."""
        return self._svc_part.restore(id_, opts)

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
