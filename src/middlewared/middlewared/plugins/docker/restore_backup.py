import errno
import logging
import os

from middlewared.api import api_method
from middlewared.api.current import DockerRestoreBackupArgs, DockerRestoreBackupResult
from middlewared.plugins.apps.ix_apps.path import get_installed_app_path
from middlewared.plugins.apps.ix_apps.utils import AppState
from middlewared.service import CallError, job, Service

from .state_utils import datasets_to_skip_for_snapshot_on_backup, docker_datasets


logger = logging.getLogger('app_lifecycle')


class DockerService(Service):

    class Config:
        cli_namespace = 'app.docker'

    @api_method(
        DockerRestoreBackupArgs, DockerRestoreBackupResult,
        audit='Docker: Restoring Backup',
        audit_extended=lambda backup_name: backup_name,
        roles=['DOCKER_WRITE']
    )
    @job(lock='docker_restore_backup')
    def restore_backup(self, job, backup_name):
        """
        Restore a backup of existing apps.
        """
        backup = self.middleware.call_sync('docker.list_backups').get(backup_name)
        if not backup:
            raise CallError(f'Backup {backup_name!r} not found', errno=errno.ENOENT)

        job.set_progress(10, 'Basic validation complete')

        logger.debug('Restoring backup %r', backup_name)
        self.middleware.call_sync('service.control', 'STOP', 'docker').wait_sync(raise_error=True)
        job.set_progress(20, 'Stopped Docker service')

        docker_config = self.middleware.call_sync('docker.config')
        self.call_sync2(
            self.s.zfs.resource.destroy_impl, os.path.join(docker_config['dataset'], 'docker'),
            bypass=True, recursive=True,
        )

        job.set_progress(25, f'Rolling back to {backup_name!r} backup')
        docker_ds, snapshot_name = backup['snapshot_name'].split('@')
        skipped_snapshot_on_backup = datasets_to_skip_for_snapshot_on_backup(docker_ds)
        for dataset in filter(lambda d: d not in skipped_snapshot_on_backup, docker_datasets(docker_ds)):
            self.call_sync2(self.s.zfs.resource.snapshot.rollback_impl, {
                'path': f'{dataset}@{snapshot_name}',
                'force': True,
                'recursive': True,
                'recursive_clones': True,
                'bypass': True,
                }
            )

        job.set_progress(30, 'Rolled back snapshots')

        self.middleware.call_sync('docker.setup.create_update_docker_datasets', docker_config['dataset'])
        self.middleware.call_sync('docker.fs_manage.mount')

        apps_to_start = []
        for app_info in backup['apps']:
            if os.path.exists(get_installed_app_path(app_info['id'])) is False:
                logger.debug('App %r path not found, skipping restoring', app_info['id'])
                continue

            if app_info['state'] == AppState.RUNNING.name:
                apps_to_start.append(app_info['id'])

        metadata_job = self.middleware.call_sync('app.metadata.generate')
        metadata_job.wait_sync()
        if metadata_job.error:
            raise CallError(f'Failed to generate app metadata: {metadata_job.error}')

        job.set_progress(50, 'Generated metadata for apps')

        self.middleware.call_sync('docker.state.start_service', True)
        job.set_progress(70, 'Started Docker service')

        logger.debug('Starting %r apps', ', '.join(apps_to_start))
        redeploy_job = self.middleware.call_sync(
            'core.bulk', 'app.redeploy', [
                [app_name] for app_name in apps_to_start
            ]
        )
        redeploy_job.wait_sync()
        # Not going to raise an error if some app failed to start as that could be true for various apps
        logger.debug('Restore complete')
        job.set_progress(100, f'Restore {backup_name!r} complete')
