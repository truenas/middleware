from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.api.current import (
    CloudSyncCreate,
    CloudSyncEntry,
    CloudSyncSyncOptions,
    CredentialsEntry,
)
from middlewared.plugins.cloud.path import get_remote_path
from middlewared.plugins.cloud.remotes import REMOTES
from middlewared.service import CallError, ServiceContext, ValidationErrors
from middlewared.utils.lang import undefined

from .crud import CloudSyncTaskFailedAlert
from .lock import FsLockDirection, local_fs_lock_manager, remote_fs_lock_manager
from .rclone import rclone

if TYPE_CHECKING:
    from middlewared.job import Job

    from .crud import CloudSyncServicePart


def do_sync(context: ServiceContext, job: Job, id_: int, options: CloudSyncSyncOptions) -> None:
    cloud_sync = context.call_sync2(context.s.cloudsync.get_instance, id_)
    if cloud_sync.locked:
        context.call_sync2(context.s.cloudsync.generate_locked_alert, id_)
        raise CallError("Dataset is locked")

    _sync(context, cloud_sync, cloud_sync.credentials, options, job)


def do_sync_onetime(
    context: ServiceContext,
    part: CloudSyncServicePart,
    job: Job,
    cloud_sync: CloudSyncCreate,
    options: CloudSyncSyncOptions,
) -> None:
    verrors = ValidationErrors()

    # Forbid unprivileged users to execute scripts as root this way.
    for k in ["pre_script", "post_script"]:
        if getattr(cloud_sync, k):
            verrors.add(
                f"cloud_sync_sync_onetime.{k}",
                "This option may not be used for onetime cloud sync operations",
            )

    # `_validate` performs the remote folder listing itself (gated on the cheap checks passing).
    part._validate(None, verrors, "cloud_sync_sync_onetime", cloud_sync)

    verrors.check()

    credentials = context.call_sync2(
        context.s.cloudsync.credentials.get_instance, part._credential_id(cloud_sync),
    )

    _sync(context, cloud_sync, credentials, options, job)


def _sync(
    context: ServiceContext,
    cloud_sync: CloudSyncEntry,
    credentials: CredentialsEntry,
    options: CloudSyncSyncOptions,
    job: Job,
) -> None:
    remote = REMOTES[credentials.provider.type]

    local_path = cloud_sync.path
    local_direction = FsLockDirection.READ if cloud_sync.direction == "PUSH" else FsLockDirection.WRITE

    remote_path = get_remote_path(remote, cloud_sync.attributes.model_dump())
    remote_direction = FsLockDirection.READ if cloud_sync.direction == "PULL" else FsLockDirection.WRITE

    directions = {
        FsLockDirection.READ: "reading",
        FsLockDirection.WRITE: "writing",
    }

    task_id = None if cloud_sync.id is undefined else cloud_sync.id  # type: ignore[comparison-overlap]

    job.set_progress(0, f"Locking local path {local_path!r} for {directions[local_direction]}")
    with local_fs_lock_manager.lock(local_path, local_direction):
        job.set_progress(0, f"Locking remote path {remote_path!r} for {directions[remote_direction]}")
        with remote_fs_lock_manager.lock(f"{credentials.id}/{remote_path}", remote_direction):
            job.set_progress(0, "Starting")
            try:
                rclone(context.middleware, job, cloud_sync, credentials, options.dry_run)
                if task_id is not None:
                    context.call_sync2(context.s.alert.oneshot_delete, "CloudSyncTaskFailed", task_id)
            except Exception:
                if task_id is not None:
                    context.call_sync2(context.s.alert.oneshot_create, CloudSyncTaskFailedAlert(
                        id=task_id,
                        name=cloud_sync.description,
                    ))
                raise


def do_abort(context: ServiceContext, id_: int) -> bool:
    cloud_sync = context.call_sync2(context.s.cloudsync.get_instance, id_)

    if cloud_sync.job is None:
        return False

    if cloud_sync.job["state"] not in ["WAITING", "RUNNING"]:
        return False

    context.middleware.call_sync("core.job_abort", cloud_sync.job["id"])
    return True


def do_restore(context: ServiceContext, id_: int, opts: Any) -> CloudSyncEntry:
    cloud_sync = context.call_sync2(context.s.cloudsync.get_instance, id_)

    data = CloudSyncCreate(
        description=opts.description,
        transfer_mode=opts.transfer_mode,
        path=opts.path,
        direction="PULL" if cloud_sync.direction == "PUSH" else "PUSH",
        credentials=cloud_sync.credentials.id,
        enabled=False,  # Do not run it automatically
        encryption=cloud_sync.encryption,
        filename_encryption=cloud_sync.filename_encryption,
        encryption_password=cloud_sync.encryption_password,
        encryption_salt=cloud_sync.encryption_salt,
        schedule=cloud_sync.schedule,
        transfers=cloud_sync.transfers,
        attributes=cloud_sync.attributes,
    )

    return context.call_sync2(context.s.cloudsync.do_create, data)
