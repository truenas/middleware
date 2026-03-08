from __future__ import annotations

import os
import typing
from datetime import datetime

from middlewared.api.current import DockerEntry, ZFSResourceSnapshotCreateQuery, ZFSResourceSnapshotDestroyQuery
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.service import CallError, ServiceContext
from middlewared.service_exception import InstanceNotFound

from .backup import delete_backup
from .backup_to_pool import incrementally_replicate_apps_dataset
from .fs_manage import mount_docker_ds, umount_docker_ds
from .state_management import set_status as docker_set_status
from .state_utils import DatasetDefaults, Status
from .utils import applications_ds_name, MIGRATION_NAMING_SCHEMA


if typing.TYPE_CHECKING:
    from middlewared.job import Job


async def migrate_ix_apps_dataset(
    context: ServiceContext, job: Job, new_config: DockerEntry, old_config: DockerEntry,
) -> None:
    # Both pools guaranteed non-None: caller validates migration requires both pools set
    assert new_config.pool is not None
    assert old_config.pool is not None
    new_pool = new_config.pool
    backup_name = f'backup_to_{new_pool}_{datetime.now().strftime("%F_%T")}'
    await docker_set_status(context, Status.MIGRATING.value)
    job.set_progress(30, 'Creating docker backup')
    backup_job = await context.call2(
        context.s.docker.backup, backup_name,  # type: ignore[call-overload,misc]
    )
    await backup_job.wait()
    if backup_job.error:
        raise CallError(f'Failed to backup docker apps: {backup_job.error}')

    job.set_progress(35, 'Stopping docker service')
    await (await context.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)

    try:
        job.set_progress(40, f'Replicating datasets from {old_config.pool!r} to {new_pool!r} pool')
        dsname = applications_ds_name(new_config.pool)
        await context.middleware.call(
            'pool.dataset.create_impl',
            CreateImplArgs(
                name=dsname,
                ztype='FILESYSTEM',
                zprops=DatasetDefaults.create_time_props(os.path.basename(dsname))
            )
        )
        if umount_job := await umount_docker_ds(context):
            await umount_job.wait()

        await replicate_apps_dataset(context, new_pool, old_config.pool)

        db_data = new_config.model_dump(mode='json', exclude={'id', 'dataset', 'nvidia'})
        await context.middleware.call('datastore.update', 'services.docker', old_config.id, db_data)

        # Mount the new pool's ix-apps so backup can be restored
        if mount_job := await mount_docker_ds(context):
            await mount_job.wait()

        job.set_progress(70, f'Restoring docker apps in {new_pool!r} pool')
        restore_job = await context.call2(
            context.s.docker.restore_backup, backup_name,  # type: ignore[call-overload,misc]
        )
        await restore_job.wait()
        if restore_job.error:
            raise CallError(f'Failed to restore docker apps on the new pool: {restore_job.error}')
    except Exception:
        await docker_set_status(context, Status.MIGRATION_FAILED.value)
        raise
    else:
        job.set_progress(100, 'Migration completed successfully')
    finally:
        await context.to_thread(delete_backup, context, backup_name)


async def replicate_apps_dataset(context: ServiceContext, new_pool: str, old_pool: str) -> None:
    # Resolve naming schema to get snapshot name
    snap_name = await context.middleware.call(
        'replication.new_snapshot_name', MIGRATION_NAMING_SCHEMA
    )
    snap_details = await context.call2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
        dataset=applications_ds_name(old_pool),
        name=snap_name,
        recursive=True,
        bypass=True,
    ))

    try:
        await incrementally_replicate_apps_dataset(context, old_pool, new_pool, MIGRATION_NAMING_SCHEMA)
    finally:
        await context.call2(context.s.zfs.resource.snapshot.destroy_impl, ZFSResourceSnapshotDestroyQuery(
            path=snap_details.name,
            recursive=True,
            bypass=True,
        ))
        target_snap_name = f'{applications_ds_name(new_pool)}@{snap_details.snapshot_name}'
        try:
            await context.call2(context.s.zfs.resource.snapshot.destroy_impl, ZFSResourceSnapshotDestroyQuery(
                path=target_snap_name,
                recursive=True,
                bypass=True,
            ))
        except InstanceNotFound:
            pass
