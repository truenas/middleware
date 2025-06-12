import errno
import logging
import os
import shutil
import yaml
from datetime import datetime

from middlewared.api import api_method
from middlewared.api.current import (
    DockerBackupArgs, DockerBackupResult, DockerListBackupArgs, DockerListBackupResult,
    DockerDeleteBackupArgs, DockerDeleteBackupResult,
)
from middlewared.plugins.apps.ix_apps.path import get_collective_config_path, get_collective_metadata_path
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name
from middlewared.service import CallError, job, Service

from .state_utils import backup_apps_state_file_path, backup_ds_path, datasets_to_skip_for_snapshot_on_backup
from .utils import BACKUP_NAME_PREFIX, UPDATE_BACKUP_PREFIX


logger = logging.getLogger('app_lifecycle')


class DockerService(Service):

    class Config:
        cli_namespace = 'app.docker'

    @api_method(
        DockerBackupArgs, DockerBackupResult,
        audit='Docker: Backup',
        audit_extended=lambda backup_name: backup_name,
        roles=['DOCKER_WRITE']
    )
    @job(lock='docker_backup')
    def backup(self, job, backup_name):
        """
        Create a backup of existing apps.

        This creates a backup of existing apps on the same pool in which docker is initialized.
        """
        self.middleware.call_sync('docker.state.validate')
        docker_config = self.middleware.call_sync('docker.config')
        name = backup_name or datetime.now().strftime('%F_%T')
        if not validate_snapshot_name(f'a@{name}'):
            # The a@ added is just cosmetic as the function requires a complete snapshot name
            # with the dataset name included in it
            raise CallError(f'{name!r} is not a valid snapshot name. It should be a valid ZFS snapshot name')

        snap_name = BACKUP_NAME_PREFIX + name
        if self.middleware.call_sync('zfs.snapshot.query', [['id', '=', f'{docker_config["dataset"]}@{snap_name}']]):
            raise CallError(f'{snap_name!r} snapshot already exists', errno=errno.EEXIST)

        if name in self.list_backups():
            raise CallError(f'Backup with {name!r} already exists', errno=errno.EEXIST)

        backup_base_dir = backup_ds_path()
        os.makedirs(backup_base_dir, exist_ok=True)
        backup_dir = os.path.join(backup_base_dir, name)
        os.makedirs(backup_dir)

        job.set_progress(10, 'Basic validation complete')

        shutil.copy(get_collective_metadata_path(), os.path.join(backup_dir, 'collective_metadata.yaml'))
        shutil.copy(get_collective_config_path(), os.path.join(backup_dir, 'collective_config.yaml'))

        with open(backup_apps_state_file_path(name), 'w') as f:
            f.write(yaml.safe_dump({app['name']: app for app in self.middleware.call_sync('app.query')}))

        with open(os.path.join(backup_dir, 'docker_config.yaml'), 'w') as f:
            f.write(yaml.safe_dump(docker_config))

        job.set_progress(95, 'Taking snapshot of ix-applications')

        self.middleware.call_sync(
            'zettarepl.create_recursive_snapshot_with_exclude', docker_config['dataset'],
            snap_name, datasets_to_skip_for_snapshot_on_backup(docker_config['dataset'])
        )

        job.set_progress(100, f'Backup {name!r} complete')

        return name

    @api_method(DockerListBackupArgs, DockerListBackupResult, roles=['DOCKER_READ'])
    def list_backups(self):
        """
        List existing app backups.
        """
        docker_config = self.middleware.call_sync('docker.config')
        if not docker_config['pool']:
            return {}

        backups_base_dir = backup_ds_path()
        backups = {}
        snapshots = self.middleware.call_sync(
            'zfs.snapshot.query', [
                ['name', '^', f'{docker_config["dataset"]}@{BACKUP_NAME_PREFIX}']
            ], {'select': ['name']}
        )
        for snapshot in snapshots:
            backup_name = snapshot['name'].split('@', 1)[-1].split(BACKUP_NAME_PREFIX, 1)[-1]
            backup_path = os.path.join(backups_base_dir, backup_name)
            if not os.path.exists(backup_path):
                continue

            try:
                with open(backup_apps_state_file_path(backup_name), 'r') as f:
                    apps = yaml.safe_load(f.read())
            except (FileNotFoundError, yaml.YAMLError):
                continue

            backups[backup_name] = {
                'name': backup_name,
                'apps': [{k: app[k] for k in ('id', 'name', 'state')} for app in apps.values()],
                'snapshot_name': snapshot['name'],
                'created_on': str(self.middleware.call_sync(
                    'zfs.snapshot.get_instance', snapshot['name']
                )['properties']['creation']['parsed']),
                'backup_path': backup_path,
            }

        return backups

    @api_method(
        DockerDeleteBackupArgs, DockerDeleteBackupResult,
        audit='Docker: Deleting Backup',
        audit_extended=lambda backup_name: backup_name,
        roles=['DOCKER_WRITE']
    )
    def delete_backup(self, backup_name):
        """
        Delete `backup_name` app backup.
        """
        self.middleware.call_sync('docker.state.validate')

        backup = self.middleware.call_sync('docker.list_backups').get(backup_name)
        if not backup:
            raise CallError(f'Backup {backup_name!r} does not exist', errno=errno.ENOENT)

        self.middleware.call_sync('zfs.snapshot.delete', backup['snapshot_name'], {'recursive': True})
        shutil.rmtree(backup['backup_path'], True)


async def post_system_update_hook(middleware):
    if not (await middleware.call('docker.config'))['dataset']:
        # If docker is not configured, there is nothing to backup
        logger.debug('Docker is not configured, skipping app\'s backup on system update')
        return

    backups = [
        v for k, v in (await middleware.call('docker.list_backups')).items()
        if k.startswith(UPDATE_BACKUP_PREFIX)
    ]
    if len(backups) >= 3:
        backups.sort(key=lambda d: d['created_on'])
        while len(backups) >= 3:
            backup = backups.pop(0)
            try:
                logger.debug('Deleting %r app\'s old auto-generated backup', backup['name'])
                await middleware.call('docker.delete_backup', backup['name'])
            except Exception as e:
                logger.error(
                    'Failed to delete %r app backup: %s', backup['name'], e, exc_info=True
                )
                break

    backup_job = await middleware.call(
        'docker.backup', f'{UPDATE_BACKUP_PREFIX}-{datetime.now().strftime("%F_%T")}'
    )
    await backup_job.wait()
    if backup_job.error:
        logger.error('Failed to backup apps: %s', backup_job.error)


async def setup(middleware):
    middleware.register_hook('update.post_update', post_system_update_hook, sync=True)
