import os

from middlewared.api import api_method
from middlewared.api.current import K8stoDockerMigrationListBackupsArgs, K8stoDockerMigrationListBackupsResult
from middlewared.service import job, Service

from .list_utils import get_backup_dir, get_default_release_details, K8s_BACKUP_NAME_PREFIX, release_details
from .utils import get_k8s_ds


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'
        cli_namespace = 'k8s_to_docker'

    @api_method(K8stoDockerMigrationListBackupsArgs, K8stoDockerMigrationListBackupsResult, roles=['DOCKER_READ'])
    @job(lock=lambda args: f'k8s_to_docker_list_backups_{args[0]}')
    def list_backups(self, job, kubernetes_pool):
        """
        List existing kubernetes backups
        """
        backup_config = {
            'error': None,
            'backups': {},
        }
        k8s_ds = get_k8s_ds(kubernetes_pool)
        if not self.middleware.call_sync('pool.dataset.query', [['id', '=', k8s_ds]]):
            return backup_config | {'error': f'Unable to locate {k8s_ds!r} dataset'}

        backup_base_dir = get_backup_dir(k8s_ds)
        if not os.path.exists(backup_base_dir):
            return backup_config | {'error': f'Unable to locate {backup_base_dir!r} backups directory'}

        self.middleware.call_sync('catalog.sync').wait_sync()

        backups = backup_config['backups']
        snapshots = self.middleware.call_sync(
            'zfs.snapshot.query', [['name', '^', f'{k8s_ds}@{K8s_BACKUP_NAME_PREFIX}']], {'select': ['name']}
        )
        releases_datasets = set(
            ds['id'].split('/', 3)[-1].split('/', 1)[0]
            for ds in self.middleware.call_sync('zfs.dataset.get_instance', f'{k8s_ds}/releases')['children']
        )
        apps_mapping = self.middleware.call_sync('catalog.train_to_apps_version_mapping')
        catalog_path = self.middleware.call_sync('catalog.config')['location']

        docker_config = self.middleware.call_sync('docker.config')
        if docker_config['pool'] and docker_config['pool'] != kubernetes_pool:
            return backup_config | {
                'error': f'Docker pool if configured must be set only to {kubernetes_pool!r} or unset'
            }

        installed_apps = {}
        if docker_config['pool'] == kubernetes_pool:
            installed_apps = {app['id']: app for app in self.middleware.call_sync('app.query')}

        for snapshot in snapshots:
            backup_name = snapshot['name'].split('@', 1)[-1].split(K8s_BACKUP_NAME_PREFIX, 1)[-1]
            backup_path = os.path.join(backup_base_dir, backup_name)
            if not os.path.exists(backup_path):
                continue

            backup_data = {
                'name': backup_name,
                'releases': [],
                'skipped_releases': [],
                'snapshot_name': snapshot['name'],
                'created_on': self.middleware.call_sync(
                    'zfs.snapshot.get_instance', snapshot['name']
                )['properties']['creation']['parsed'],
                'backup_path': backup_path,
            }

            with os.scandir(backup_path) as entries:
                for release in entries:
                    if release.name not in releases_datasets:
                        backup_data['skipped_releases'].append(get_default_release_details(release.name) | {
                            'error': 'Release dataset not found in releases dataset',
                        })
                        continue

                    config = release_details(
                        release.name, release.path, catalog_path, apps_mapping, installed_apps,
                    )
                    if config['error']:
                        backup_data['skipped_releases'].append(config)
                    else:
                        backup_data['releases'].append(config)

            backups[backup_name] = backup_data

        job.set_progress(100, 'Retrieved backup config')
        return backup_config
