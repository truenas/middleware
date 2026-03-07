from __future__ import annotations

import errno
import logging
import os
import typing

from middlewared.api.current import ZFSResourceSnapshotRollbackQuery
from middlewared.plugins.apps.ix_apps.path import get_installed_app_path
from middlewared.plugins.apps.ix_apps.utils import AppState
from middlewared.service import CallError, ServiceContext

from .backup import list_backups
from .fs_manage import mount_docker_ds
from .state_management import start_service
from .state_setup import create_update_docker_datasets
from .state_utils import datasets_to_skip_for_snapshot_on_backup, docker_datasets


if typing.TYPE_CHECKING:
    from middlewared.job import Job


logger = logging.getLogger('app_lifecycle')


def restore_backup(context: ServiceContext, job: Job, backup_name: str) -> None:
    backup = list_backups(context).root.get(backup_name)
    if not backup:
        raise CallError(f'Backup {backup_name!r} not found', errno=errno.ENOENT)

    job.set_progress(10, 'Basic validation complete')

    logger.debug('Restoring backup %r', backup_name)
    context.middleware.call_sync('service.control', 'STOP', 'docker').wait_sync(raise_error=True)
    job.set_progress(20, 'Stopped Docker service')

    docker_config = context.call_sync2(context.s.docker.config)
    assert docker_config.dataset is not None
    context.call_sync2(
        context.s.zfs.resource.destroy_impl, os.path.join(docker_config.dataset, 'docker'),
        bypass=True, recursive=True,
    )

    job.set_progress(25, f'Rolling back to {backup_name!r} backup')
    docker_ds, snapshot_name = backup.snapshot_name.split('@')
    skipped_snapshot_on_backup = datasets_to_skip_for_snapshot_on_backup(docker_ds)
    for dataset in filter(lambda d: d not in skipped_snapshot_on_backup, docker_datasets(docker_ds)):
        context.call_sync2(context.s.zfs.resource.snapshot.rollback_impl, ZFSResourceSnapshotRollbackQuery(
            path=f'{dataset}@{snapshot_name}',
            force=True,
            recursive=True,
            recursive_clones=True,
            bypass=True,
        ))

    job.set_progress(30, 'Rolled back snapshots')

    create_update_docker_datasets(context, docker_config.dataset)
    context.run_coroutine(mount_docker_ds(context))

    apps_to_start = []
    for app_info in backup.apps:
        if os.path.exists(get_installed_app_path(app_info.id)) is False:
            logger.debug('App %r path not found, skipping restoring', app_info.id)
            continue

        if app_info.state == AppState.RUNNING.name:
            apps_to_start.append(app_info.id)

    metadata_job = context.middleware.call_sync('app.metadata.generate')
    metadata_job.wait_sync()
    if metadata_job.error:
        raise CallError(f'Failed to generate app metadata: {metadata_job.error}')

    job.set_progress(50, 'Generated metadata for apps')

    context.run_coroutine(start_service(context, True))
    job.set_progress(70, 'Started Docker service')

    logger.debug('Starting %r apps', ', '.join(apps_to_start))
    redeploy_job = context.middleware.call_sync(
        'core.bulk', 'app.redeploy', [
            [app_name] for app_name in apps_to_start
        ]
    )
    redeploy_job.wait_sync()
    # Not going to raise an error if some app failed to start as that could be true for various apps
    logger.debug('Restore complete')
    job.set_progress(100, f'Restore {backup_name!r} complete')
