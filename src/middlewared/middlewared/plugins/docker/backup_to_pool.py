from __future__ import annotations

import logging
import typing

from middlewared.alert.source.applications import DockerBackupToPoolFailedAlert
from middlewared.api.current import (
    ZFSResourceQuery,
    ZFSResourceSnapshotCreateQuery,
    ZFSResourceSnapshotDestroyQuery,
    ZFSResourceSnapshotQuery,
)
from middlewared.plugins.zfs.utils import get_encryption_info
from middlewared.service import CallError, ServiceContext, ValidationErrors
from middlewared.utils.zfs import query_imported_fast_impl

from .state_utils import Status
from .utils import applications_ds_name

if typing.TYPE_CHECKING:
    from middlewared.job import Job


logger = logging.getLogger('app_lifecycle')

# Number of source-side automated-backup snapshots to keep. Only the most recent one is needed as the base
# for the next incremental replication; older ones would otherwise accumulate forever on an automated schedule.
SOURCE_BACKUP_SNAPSHOT_RETENTION = 1

# User property set on snapshots created by the automated (scheduled) backup. Manual backup_to_pool snapshots
# share the same naming schema (so they form one incremental lineage) but are left untagged, which lets the
# pruning below distinguish and only delete automated snapshots without touching operator-created ones.
AUTOMATED_BACKUP_PROP = 'truenas:automated_app_backup'


def backup_to_pool_snapshot_prefix(source_pool: str, target_pool: str) -> str:
    return f'ix-apps-{source_pool}-to-{target_pool}-backup-'


def backup_to_pool_snapshot_schema(source_pool: str, target_pool: str) -> str:
    return f'{backup_to_pool_snapshot_prefix(source_pool, target_pool)}%Y-%m-%d_%H-%M-%S'


async def backup_to_pool(context: ServiceContext, job: Job, target_pool: str, automated: bool = False) -> None:
    verrors = ValidationErrors()
    docker_config = await context.call2(context.s.docker.config)
    if docker_config.pool is None:
        verrors.add('pool', 'Docker is not configured to use a pool')
    if target_pool == docker_config.pool:
        verrors.add('target_pool', 'Target pool cannot be the same as the current Docker pool')

    verrors.check()

    target_root_ds = await context.call2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[target_pool], properties=['encryption'])
    )
    if not target_root_ds:
        verrors.add('target_pool', 'Target pool does not exist')
    elif get_encryption_info(target_root_ds[0]['properties']).encrypted:
        # This is not allowed because destination root if encrypted means that docker datasets would be
        # not encrypted and by design we don't allow this to happen to keep it simple / straight forward.
        # https://github.com/truenas/zettarepl/blob/52d3b7a00fa4630c3428ae4e70bc33cf41a6d768/zettarepl/
        # replication/run.py#L319
        verrors.add('target_pool', f'Backup to an encrypted pool {target_pool!r} is not allowed')

    verrors.check()

    assert docker_config.pool is not None
    job.set_progress(10, 'Initial validation has been completed, stopping docker service')
    await (await context.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)
    job.set_progress(30, 'Snapshotting apps dataset')
    schema = backup_to_pool_snapshot_schema(docker_config.pool, target_pool)
    try:
        # Resolve naming schema to get snapshot name
        snap_name = await context.middleware.call(
            'replication.new_snapshot_name', schema
        )
        await context.call2(context.s.zfs.resource.snapshot.create_impl, ZFSResourceSnapshotCreateQuery(
            dataset=applications_ds_name(docker_config.pool),
            name=snap_name,
            recursive=True,
            bypass=True,
            user_properties={AUTOMATED_BACKUP_PROP: '1'} if automated else {},
        ))
    finally:
        # We do this in try/finally block to ensure that docker service is started back
        await (await context.middleware.call('service.control', 'START', 'docker')).wait(raise_error=True)

    job.set_progress(45, 'Incrementally replicating apps dataset')

    try:
        await incrementally_replicate_apps_dataset(context, docker_config.pool, target_pool, schema)
    except Exception:
        job.set_progress(90, 'Failed to incrementally replicate apps dataset')
        raise
    else:
        job.set_progress(100, 'Successfully incrementally replicated apps dataset')


async def incrementally_replicate_apps_dataset(
    context: ServiceContext, source_pool: str, target_pool: str, schema: str
) -> None:
    old_ds = applications_ds_name(source_pool)
    new_ds = applications_ds_name(target_pool)
    replication_job = await context.middleware.call(
        'replication.run_onetime', {
            'direction': 'PUSH',
            'transport': 'LOCAL',
            'source_datasets': [old_ds],
            'target_dataset': new_ds,
            'recursive': True,
            'also_include_naming_schema': [schema],
            'retention_policy': 'SOURCE',
            'replicate': True,
            'readonly': 'IGNORE',
            'exclude_mountpoint_property': True,
            'mount': False,
        }
    )
    await replication_job.wait()
    if replication_job.error:
        raise CallError(f'Failed to migrate {old_ds} to {new_ds}: {replication_job.error}')


async def prune_source_backup_snapshots(context: ServiceContext, source_pool: str, target_pool: str) -> None:
    """
    Delete older automated-backup snapshots on the source apps dataset, keeping the most recent one as the
    base for the next incremental replication. ``retention_policy=SOURCE`` only prunes the target side, so
    without this the source would accumulate one recursive snapshot per scheduled run indefinitely.

    Only snapshots tagged with ``AUTOMATED_BACKUP_PROP`` are considered, so operator-created (manual)
    backup_to_pool snapshots are never pruned even though they share the same naming schema.
    """
    source_ds = applications_ds_name(source_pool)
    prefix = backup_to_pool_snapshot_prefix(source_pool, target_pool)
    snapshots = await context.call2(
        context.s.zfs.resource.snapshot.query,
        ZFSResourceSnapshotQuery(paths=[source_ds], properties=['creation'], get_user_properties=True),
    )
    matching: list[tuple[float, str]] = []
    for snap in (snapshots or []):
        if not snap.name.split('@', 1)[-1].startswith(prefix):
            continue
        if not snap.user_properties or snap.user_properties.get(AUTOMATED_BACKUP_PROP) != '1':
            continue
        if snap.properties is None or snap.properties.creation.value is None:
            continue
        matching.append((float(snap.properties.creation.value), snap.name))

    matching.sort(key=lambda item: item[0])
    to_delete = matching[:-SOURCE_BACKUP_SNAPSHOT_RETENTION] if SOURCE_BACKUP_SNAPSHOT_RETENTION else matching
    for _creation, snap_name in to_delete:
        try:
            await context.call2(
                context.s.zfs.resource.snapshot.destroy_impl,
                ZFSResourceSnapshotDestroyQuery(path=snap_name, recursive=True, bypass=True),
            )
        except Exception:
            logger.warning('%s: failed to prune old apps backup snapshot', snap_name, exc_info=True)


async def scheduled_backup_to_pool(context: ServiceContext, job: Job) -> None:
    """
    Entry point invoked by cron to run the automated apps-dataset backup to the configured target pool.

    It re-checks at runtime that the operation can proceed (the crontab line is static between regenerations,
    so the configuration or pool state may have changed) and surfaces blocking conditions/failures as a
    one-shot alert rather than failing noisily.
    """
    config = await context.call2(context.s.docker.config)
    if not config.backup_to_pool_enabled:
        logger.debug('Automated apps backup is disabled, skipping scheduled run')
        return

    target = config.backup_to_pool_target

    async def skip_with_alert(reason: str) -> None:
        logger.warning('Skipping scheduled apps backup to %r: %s', target, reason)
        await context.call2(
            context.s.alert.oneshot_create,
            DockerBackupToPoolFailedAlert(target=target or 'unknown', error=reason),
        )

    if not config.pool or not await context.to_thread(query_imported_fast_impl, [config.pool]):
        await skip_with_alert('the Docker pool is not configured or not imported')
        return

    if (await context.call2(context.s.docker.status)).status in (
        Status.MIGRATING.value, Status.MIGRATION_FAILED.value,
    ):
        # Migration owns the apps dataset/docker service; don't interfere. Transient, so no alert.
        logger.debug('Apps are migrating, skipping scheduled apps backup')
        return

    if not target:
        await skip_with_alert('no target pool is configured')
        return

    target_root = await context.call2(
        context.s.zfs.resource.query_impl, ZFSResourceQuery(paths=[target], properties=['encryption'])
    )
    if not target_root:
        await skip_with_alert('the target pool does not exist or is not imported')
        return
    if get_encryption_info(target_root[0]['properties']).encrypted:
        await skip_with_alert('the target pool is encrypted')
        return

    try:
        await backup_to_pool(context, job, target, automated=True)
    except Exception as e:
        logger.error('Scheduled apps backup to %r failed', target, exc_info=True)
        await context.call2(
            context.s.alert.oneshot_create,
            DockerBackupToPoolFailedAlert(target=target, error=str(e)),
        )
        raise

    assert config.pool is not None
    await prune_source_backup_snapshots(context, config.pool, target)
    await context.call2(context.s.alert.oneshot_delete, 'DockerBackupToPoolFailed')
