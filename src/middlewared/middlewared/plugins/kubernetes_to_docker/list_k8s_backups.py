import os

from middlewared.schema import accepts, Dict, returns, Str
from middlewared.service import Service

from .list_utils import get_backup_dir, K8s_BACKUP_NAME_PREFIX
from .utils import get_k8s_ds


class K8stoDockerMigrationService(Service):

    class Config:
        namespace = 'k8s_to_docker'
        cli_namespace = 'k8s_to_docker'

    @accepts(Str('kubernetes_pool'))
    @returns(Dict(
        'backups',
        Str('error', null=True),
        Dict('backups', additional_attrs=True),
    ))
    def list_backups(self, kubernetes_pool):
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

        backups = backup_config['backups']
        snapshots = self.middleware.call_sync(
            'zfs.snapshot.query', [['name', '^', f'{k8s_ds}@{K8s_BACKUP_NAME_PREFIX}']], {'select': ['name']}
        )
        releases_datasets = set(
            ds['id'].split('/', 3)[-1].split('/', 1)[0]
            for ds in self.middleware.call_sync('zfs.dataset.get_instance', f'{k8s_ds}/releases')['children']
        )

        for snapshot in snapshots:
            backup_name = snapshot['name'].split('@', 1)[-1].split(K8s_BACKUP_NAME_PREFIX, 1)[-1]
            backup_path = os.path.join(backup_base_dir, backup_name)
            if not os.path.exists(backup_path):
                continue

            backup_data = {
                'name': backup_name,
                'releases': [],
                'snapshot_name': snapshot['name'],
                'created_on': self.middleware.call_sync(
                    'zfs.snapshot.get_instance', snapshot['name']
                )['properties']['creation']['parsed'],
                'backup_path': backup_path,
            }

            with os.scandir(backup_path) as entries:
                for release in filter(lambda r: r.name in releases_datasets, entries):
                    backup_data['releases'].append(release.name)

            for release in filter(lambda r: r in releases_datasets, os.listdir(backup_path)):
                backup_data['releases'].append(release)

            backups[backup_name] = backup_data

        return backup_config
