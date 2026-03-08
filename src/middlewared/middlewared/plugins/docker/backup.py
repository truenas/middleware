from __future__ import annotations

import datetime
import errno
import logging
import os
import shutil
import typing
import yaml

from middlewared.api.current import (
    DockerBackupAppInfo, DockerBackupEntry, DockerBackupMap,
    ZFSResourceQuery, ZFSResourceSnapshotQuery, ZFSResourceSnapshotDestroyQuery,
)
from middlewared.plugins.apps.ix_apps.path import get_collective_config_path, get_collective_metadata_path
from middlewared.plugins.apps.ix_apps.utils import dump_yaml
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name
from middlewared.service import CallError, ServiceContext
from middlewared.utils.io import atomic_write

from .state_management import validate_state
from .state_utils import backup_apps_state_file_path, backup_ds_path, datasets_to_skip_for_snapshot_on_backup
from .utils import BACKUP_NAME_PREFIX, UPDATE_BACKUP_PREFIX


if typing.TYPE_CHECKING:
    from middlewared.job import Job
    from middlewared.main import Middleware


logger = logging.getLogger('app_lifecycle')


def list_backups(context: ServiceContext) -> DockerBackupMap:
    docker_config = context.call_sync2(context.s.docker.config)
    if not docker_config.pool:
        return DockerBackupMap(root={})

    backups_base_dir = backup_ds_path()
    backups: dict[str, DockerBackupEntry] = {}
    # Check if the dataset exists
    ds = context.call_sync2(
        context.s.zfs.resource.query_impl,
        ZFSResourceQuery(paths=[docker_config.dataset], properties=None)
    )
    if not ds:
        return DockerBackupMap(root=backups)

    # Get snapshots for the dataset (properties: None for efficiency)
    snapshots = context.call_sync2(context.s.zfs.resource.snapshot.query, ZFSResourceSnapshotQuery(
        paths=[docker_config.dataset],
        properties=['creation'],
    ))
    if not snapshots:
        return DockerBackupMap(root=backups)

    prefix = f'{docker_config.dataset}@{BACKUP_NAME_PREFIX}'
    for snap in snapshots:
        snap_name = snap.name
        if not snap_name.startswith(prefix):
            continue

        backup_name = snap_name.split('@', 1)[-1].split(BACKUP_NAME_PREFIX, 1)[-1]
        backup_path = os.path.join(backups_base_dir, backup_name)
        if not os.path.exists(backup_path):
            continue

        try:
            with open(backup_apps_state_file_path(backup_name), 'r') as f:
                apps = yaml.safe_load(f.read())
        except (FileNotFoundError, yaml.YAMLError):
            continue

        if snap.properties is None or snap.properties.creation.value is None:
            continue

        backups[backup_name] = DockerBackupEntry(
            name=backup_name,
            apps=[DockerBackupAppInfo(id=app['id'], name=app['name'], state=app['state']) for app in apps.values()],
            snapshot_name=snap_name,
            created_on=str(
                datetime.datetime.fromtimestamp(
                    float(snap.properties.creation.value),
                    datetime.UTC
                )
            ),
            backup_path=backup_path,
        )

    return DockerBackupMap(backups)


def backup(context: ServiceContext, job: Job, backup_name: str | None) -> str:
    context.run_coroutine(validate_state(context))
    docker_config = context.call_sync2(context.s.docker.config)
    name = backup_name or datetime.datetime.now().strftime('%F_%T')
    if not validate_snapshot_name(f'a@{name}'):
        # The a@ added is just cosmetic as the function requires a complete snapshot name
        # with the dataset name included in it
        raise CallError(f'{name!r} is not a valid snapshot name. It should be a valid ZFS snapshot name')

    snap_name = BACKUP_NAME_PREFIX + name
    snap_path = f'{docker_config.dataset}@{snap_name}'
    if context.call_sync2(context.s.zfs.resource.snapshot.exists, snap_path):
        raise CallError(f'{snap_name!r} snapshot already exists', errno=errno.EEXIST)

    if name in list_backups(context).root:
        raise CallError(f'Backup with {name!r} already exists', errno=errno.EEXIST)

    backup_base_dir = backup_ds_path()
    os.makedirs(backup_base_dir, exist_ok=True)
    backup_dir = os.path.join(backup_base_dir, name)
    os.makedirs(backup_dir)

    job.set_progress(10, 'Basic validation complete')

    shutil.copy(get_collective_metadata_path(), os.path.join(backup_dir, 'collective_metadata.yaml'))
    shutil.copy(get_collective_config_path(), os.path.join(backup_dir, 'collective_config.yaml'))

    with atomic_write(backup_apps_state_file_path(name), 'w') as f:
        f.write(dump_yaml(
            {app['name']: app for app in context.middleware.call_sync('app.query')})
        )

    with atomic_write(os.path.join(backup_dir, 'docker_config.yaml'), 'w') as f:
        f.write(dump_yaml(docker_config.model_dump()))

    job.set_progress(95, 'Taking snapshot of ix-applications')

    assert docker_config.dataset is not None
    context.middleware.call_sync(
        'zettarepl.create_recursive_snapshot_with_exclude', docker_config.dataset,
        snap_name, datasets_to_skip_for_snapshot_on_backup(docker_config.dataset)
    )

    job.set_progress(100, f'Backup {name!r} complete')

    return name


def delete_backup(context: ServiceContext, backup_name: str) -> None:
    context.run_coroutine(validate_state(context))

    backup = list_backups(context).root.get(backup_name)
    if not backup:
        raise CallError(f'Backup {backup_name!r} does not exist', errno=errno.ENOENT)

    context.call_sync2(
        context.s.zfs.resource.snapshot.destroy_impl,
        ZFSResourceSnapshotDestroyQuery(
            path=backup.snapshot_name,
            recursive=True,
            bypass=True,
        ),
    )
    shutil.rmtree(backup.backup_path, True)


async def post_system_update_hook(middleware: Middleware) -> None:
    if not (await middleware.call2(middleware.s.docker.config)).dataset:
        # If docker is not configured, there is nothing to backup
        logger.debug('Docker is not configured, skipping apps backup on system update')
        return

    backups = []
    for k, v in (await middleware.call2(middleware.s.docker.list_backups)).root.items():
        if k.startswith(UPDATE_BACKUP_PREFIX):
            backups.append(v)

    if len(backups) >= 3:
        backups.sort(key=lambda d: d.created_on)
        while len(backups) >= 3:
            backup = backups.pop(0)
            try:
                logger.debug('Deleting %r apps old auto-generated backup', backup.name)
                await middleware.call2(middleware.s.docker.delete_backup, backup.name)
            except Exception as e:
                logger.error(
                    'Failed to delete %r app backup: %s', backup.name, e, exc_info=True
                )
                break

    backup_job: Job = await middleware.call2(
        middleware.s.docker.backup,
        f'{UPDATE_BACKUP_PREFIX}-{datetime.datetime.now().strftime("%F_%T")}'  # type: ignore[misc,arg-type]
    )
    await backup_job.wait()
    if backup_job.error:
        logger.error('Failed to backup apps: %s', backup_job.error)
