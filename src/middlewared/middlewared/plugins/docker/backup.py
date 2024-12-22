import errno
import os
import shutil
import yaml
from datetime import datetime

from middlewared.api import api_method
from middlewared.api.current import DockerUpdateArgs, DockerBackupResult
from middlewared.plugins.apps.ix_apps.path import get_collective_config_path, get_collective_metadata_path
from middlewared.plugins.zfs_.validation_utils import validate_snapshot_name
from middlewared.service import CallError, job, private, Service

from .state_utils import backup_ds_path, datasets_to_skip_for_snapshot_on_backup
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

        # TODO: Add listing backups functionality
        # if name in self.list_backups():
        #    raise CallError(f'Backup with {name!r} already exists', errno=errno.EEXIST)

        backup_base_dir = backup_ds_path()
        os.makedirs(backup_base_dir, exist_ok=True)
        backup_dir = os.path.join(backup_base_dir, name)
        os.makedirs(backup_dir)

        job.set_progress(10, 'Basic validation complete')

        shutil.copy(get_collective_metadata_path(), os.path.join(backup_dir, 'collective_metadata.yaml'))
        shutil.copy(get_collective_config_path(), os.path.join(backup_dir, 'collective_config.yaml'))

        with open(os.path.join(backup_dir, 'apps_state.yaml'), 'w') as f:
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
