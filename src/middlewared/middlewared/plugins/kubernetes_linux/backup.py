import errno
import json
import os

from datetime import datetime

from middlewared.schema import Str
from middlewared.service import accepts, CallError, job, Service

from .utils import BACKUP_NAME_PREFIX


class KubernetesService(Service):

    @accepts(
        Str('backup_name', null=True, default=None)
    )
    @job(lock='chart_releases_backup')
    def backup_chart_releases(self, job, backup_name):
        self.middleware.call_sync('kubernetes.validate_k8s_setup')
        name = backup_name or datetime.utcnow().strftime('%F_%T')
        snap_name = BACKUP_NAME_PREFIX + name
        if self.middleware.call_sync('zfs.snapshot.query', [['name', '=', snap_name]]):
            raise CallError(f'{snap_name!r} snapshot already exists', errno=errno.EEXIST)

        if name in self.list_backups():
            raise CallError(f'Backup with {name!r} already exists', errno=errno.EEXIST)

        k8s_config = self.middleware.call_sync('kubernetes.config')
        backup_base_dir = os.path.join('/mnt', k8s_config['dataset'], 'backups')
        os.makedirs(backup_base_dir, exist_ok=True)
        backup_dir = os.path.join(backup_base_dir, name)
        os.makedirs(backup_dir)

        job.set_progress(10, 'Basic validation complete')
        chart_releases = self.middleware.call_sync('chart.release.query', [], {'extra': {'retrieve_resources': True}})
        len_chart_releases = len(chart_releases)
        for index, chart_release in enumerate(chart_releases):
            job.set_progress(
                10 + ((index + 1) / len_chart_releases) * 80, f'Backing up {chart_release["name"]}'
            )
            chart_release_backup_path = os.path.join(backup_dir, chart_release['name'])
            os.makedirs(chart_release_backup_path)
            with open(os.path.join(chart_release_backup_path, 'namespace.yaml'), 'w') as f:
                f.write(self.middleware.call_sync('k8s.namespace.export_to_yaml', chart_release['namespace']))

            secrets_dir = os.path.join(chart_release_backup_path, 'secrets')
            os.makedirs(secrets_dir)

            secrets = self.middleware.call_sync(
                'k8s.secret.query', [
                    ['type', '=', 'helm.sh/release.v1'], ['metadata.namespace', '=', chart_release['namespace']]
                ]
            )
            for secret in sorted(secrets, key=lambda d: d['metadata']['name']):
                with open(os.path.join(secrets_dir, secret['metadata']['name']), 'w') as f:
                    f.write(self.middleware.call_sync('k8s.secret.export_to_yaml_internal', secret))

            with open(os.path.join(chart_release_backup_path, 'workloads_replica_counts.json'), 'w') as f:
                f.write(json.dumps(self.middleware.call_sync(
                    'chart.release.get_replica_count_for_resources', chart_release['resources'],
                )))

        job.set_progress(95, 'Taking snapshot of ix-applications')

        self.middleware.call_sync(
            'zfs.snapshot.create', {'dataset': k8s_config['dataset'], 'name': snap_name, 'recursive': True}
        )

        job.set_progress(100, f'Backup {name!r} complete')

    @accepts()
    def list_backups(self):
        self.middleware.call_sync('kubernetes.validate_k8s_setup')
        k8s_config = self.middleware.call_sync('kubernetes.config')
        backup_base_dir = os.path.join('/mnt', k8s_config['dataset'], 'backups')

        backups = {}
        snapshots = self.middleware.call_sync(
            'zfs.snapshot.query', [['name', '^', f'{k8s_config["dataset"]}@{BACKUP_NAME_PREFIX}']], {'select': ['name']}
        )
        releases_datasets = set(
            ds['id'].split('/', 3)[-1].split('/', 1)[0] for ds in self.middleware.call_sync(
                'pool.dataset.query', [['id', '=', f'{k8s_config["dataset"]}/releases']], {'get': True},
            )['children']
        )

        for snapshot in snapshots:
            backup_name = snapshot['name'].split('@', 1)[-1].split(BACKUP_NAME_PREFIX, 1)[-1]
            backup_path = os.path.join(backup_base_dir, backup_name)
            if not os.path.exists(backup_path):
                continue

            backup_data = {
                'releases': [],
                'snapshot_name': snapshot['name'],
                'created_on': self.middleware.call_sync(
                    'zfs.snapshot.get_instance', snapshot['name']
                )['properties']['creation']['parsed'],
            }

            for release in filter(lambda r: r in releases_datasets, os.listdir(backup_path)):
                backup_data['releases'].append(release)

            backups[backup_name] = backup_data

        return backups
