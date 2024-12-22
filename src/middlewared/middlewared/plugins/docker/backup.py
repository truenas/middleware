import errno
import os
import shutil
import yaml
from datetime import datetime

from middlewared.api import api_method
from middlewared.api.current import (
    DockerBackupResult, DockerUpdateArgs, DockerListBackupArgs, DockerListBackupResult, DockerDeleteBackupArgs,
    DockerDeleteBackupResult,
)
from middlewared.plugins.apps.ix_apps.path import get_collective_config_path, get_collective_metadata_path
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name
from middlewared.service import CallError, job, Service

from .state_utils import backup_apps_state_file_path, backup_ds_path, datasets_to_skip_for_snapshot_on_backup
from .utils import BACKUP_NAME_PREFIX


class DockerService(Service):

    class Config:
        cli_namespace = 'app.docker'

    @api_method(DockerUpdateArgs, DockerBackupResult, roles=['DOCKER_WRITE'])
    @job(lock='docker_backup')
    def backup(self, job, backup_name):
        """
        Create a backup of existing apps.
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

        with open(backup_apps_state_file_path(), 'w') as f:
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
                with open(backup_apps_state_file_path(), 'r') as f:
                    apps = yaml.safe_load(f.read())
            except (FileNotFoundError, yaml.YAMLError):
                continue

            backups[backup_name] = {
                'name': backup_name,
                'apps': list(apps),
                'snapshot_name': snapshot['name'],
                'created_on': self.middleware.call_sync(
                    'zfs.snapshot.get_instance', snapshot['name']
                )['properties']['creation']['parsed'],
                'backup_path': backup_path,
            }

        return backups

    @api_method(DockerDeleteBackupArgs, DockerDeleteBackupResult, roles=['DOCKER_WRITE'])
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
