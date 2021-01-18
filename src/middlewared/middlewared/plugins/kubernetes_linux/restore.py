import errno
import json
import os
import shutil
import time
import yaml

from middlewared.schema import Str
from middlewared.service import accepts, CallError, job, Service


class KubernetesService(Service):

    @accepts(Str('backup_name'))
    @job(lock='kubernetes_restore_backup')
    def restore_backup(self, job, backup_name):
        """
        Restore `backup_name` chart releases backup.

        It should be noted that a rollback will be initiated which will destroy any newer snapshots/clones
        of `ix-applications` dataset then the snapshot in question of `backup_name`.
        """
        self.middleware.call_sync('kubernetes.validate_k8s_setup')
        backup = self.middleware.call_sync('kubernetes.list_backups').get(backup_name)
        if not backup:
            raise CallError(f'Backup {backup_name!r} does not exist', errno=errno.ENOENT)

        job.set_progress(5, 'Basic validation complete')

        self.middleware.call_sync('service.stop', 'kubernetes')
        shutil.rmtree('/etc/rancher', True)
        db_config = self.middleware.call_sync('datastore.config', 'services.kubernetes')
        self.middleware.call_sync('datastore.update', 'services.kubernetes', db_config['id'], {'cni_config': {}})

        k8s_config = self.middleware.call_sync('kubernetes.config')
        self.middleware.call_sync(
            'zfs.snapshot.rollback', backup['snapshot_name'], {
                'force': True,
                'recursive': True,
                'recursive_clones': True,
            }
        )

        # FIXME: Remove this sleep, sometimes the k3s dataset fails to umount
        #  After discussion with mav, it sounds like a bug to him in zfs, so until that is fixed, we have this sleep
        time.sleep(20)

        k3s_ds = os.path.join(k8s_config['dataset'], 'k3s')
        self.middleware.call_sync('zfs.dataset.delete', k3s_ds, {'force': True, 'recursive': True})
        self.middleware.call_sync('zfs.dataset.create', {'name': k3s_ds, 'type': 'FILESYSTEM'})
        self.middleware.call_sync('zfs.dataset.mount', k3s_ds)

        self.middleware.call_sync('service.start', 'kubernetes')

        while True:
            config = self.middleware.call_sync('k8s.node.config')
            if config['node_configured'] and not config['spec']['taints']:
                break
            time.sleep(5)

        job.set_progress(30, 'Kubernetes cluster re-initialized')

        backup_dir = backup['backup_path']
        releases_datasets = set(
            ds['id'].split('/', 3)[-1].split('/', 1)[0] for ds in self.middleware.call_sync(
                'zfs.dataset.get_instance', f'{k8s_config["dataset"]}/releases'
            )['children']
        )

        releases = os.listdir(backup_dir)
        len_releases = len(releases)
        restored_chart_releases = {}

        for index, release_name in enumerate(releases):
            job.set_progress(
                30 + ((index + 1) / len_releases) * 60,
                f'Restoring helm configuration for {release_name!r} chart release'
            )

            if release_name not in releases_datasets:
                self.logger.error(
                    'Skipping backup of %r chart release due to missing chart release dataset', release_name
                )
                continue

            r_backup_dir = os.path.join(backup_dir, release_name)
            if any(
                not os.path.exists(os.path.join(r_backup_dir, f)) for f in ('namespace.yaml', 'secrets')
            ) or not os.listdir(os.path.join(r_backup_dir, 'secrets')):
                self.logger.error(
                    'Skipping backup of %r chart release due to missing configuration files', release_name
                )
                continue

            # First we will restore namespace and then the secrets
            with open(os.path.join(r_backup_dir, 'namespace.yaml'), 'r') as f:
                namespace_body = yaml.load(f.read(), Loader=yaml.FullLoader)
                self.middleware.call_sync('k8s.namespace.create', {'body': namespace_body})

            secrets_dir = os.path.join(r_backup_dir, 'secrets')
            for secret in sorted(os.listdir(secrets_dir)):
                with open(os.path.join(secrets_dir, secret)) as f:
                    self.middleware.call_sync(
                        'k8s.secret.create', {
                            'namespace': namespace_body['metadata']['name'],
                            'body': yaml.load(f.read(), Loader=yaml.FullLoader),
                        }
                    )

            with open(os.path.join(r_backup_dir, 'workloads_replica_counts.json'), 'r') as f:
                restored_chart_releases[release_name] = {'replica_counts': json.loads(f.read())}

        # Now helm will recognise the releases as valid, however we don't have any actual k8s deployed resource
        # That will be adjusted with updating chart releases with their existing values and helm will see that
        # k8s resources don't exist and will create them for us
        job.set_progress(92, 'Creating kubernetes resources')
        update_jobs = []
        for chart_release in restored_chart_releases:
            update_jobs.append(self.middleware.call_sync('chart.release.update', chart_release, {'values': {}}))

        for update_job in update_jobs:
            update_job.wait_sync()

        job.set_progress(95, 'Scaling scalable workloads')
        for chart_release in self.middleware.call_sync(
            'chart.release.query', [], {'extra': {'retrieve_resources': True}}
        ):
            restored_chart_releases[chart_release['name']]['resources'] = chart_release['resources']

        for chart_release in restored_chart_releases.values():
            self.middleware.call_sync(
                'chart.release.scale_release_internal', chart_release['resources'], None,
                chart_release['replica_counts'], True,
            )

        job.set_progress(100, f'Restore of {backup_name!r} backup complete')
