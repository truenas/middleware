import collections
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

        # Add taint to force stop pods
        self.middleware.call_sync('k8s.node.add_taints', [{'key': 'ix-stop-cluster', 'effect': 'NoExecute'}])

        for container in self.middleware.call_sync('docker.container.query'):
            try:
                self.middleware.call_sync('docker.container.delete', container['id'])
            except CallError:
                # This is okay - we just want to make sure there are no leftover datasets and it's possible that
                # because of the taint, we have containers being removed
                pass

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
                'recursive_rollback': True,
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
        restored_chart_releases = collections.defaultdict(lambda: {'pv_info': {}})

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
                restored_chart_releases[release_name]['replica_counts'] = json.loads(f.read())

            pv_info_path = os.path.join(r_backup_dir, 'pv_info.json')
            if os.path.exists(pv_info_path):
                with open(pv_info_path, 'r') as f:
                    restored_chart_releases[release_name]['pv_info'] = json.loads(f.read())

        self.middleware.call_sync('k8s.node.add_taints', [{'key': 'ix-backup-restore', 'effect': 'NoExecute'}])
        # Now helm will recognise the releases as valid, however we don't have any actual k8s deployed resource
        # That will be adjusted with updating chart releases with their existing values and helm will see that
        # k8s resources don't exist and will create them for us
        job.set_progress(92, 'Creating kubernetes resources')
        update_jobs = []
        for chart_release in restored_chart_releases:
            self.middleware.call_sync(
                'chart.release.create_update_storage_class_for_chart_release',
                chart_release, os.path.join(k8s_config['dataset'], 'releases', chart_release)
            )
            update_jobs.append(self.middleware.call_sync('chart.release.update', chart_release, {'values': {}}))

        for update_job in update_jobs:
            update_job.wait_sync()

        # We should have k8s resources created now. Now a new PVC will be created as k8s won't retain the original
        # information which was in it's state at backup time. We will get current dataset mapping and then
        # rename old ones which were mapped to the same PVC to have the new name
        chart_releases = {
            c['name']: c for c in self.middleware.call_sync(
                'chart.release.query', [], {'extra': {'retrieve_resources': True}}
            )
        }

        for release_name in list(restored_chart_releases):
            if release_name not in chart_releases:
                restored_chart_releases.pop(release_name)
            else:
                restored_chart_releases[release_name]['resources'] = chart_releases[release_name]['resources']

        datasets = set(
            d['id'] for d in self.middleware.call_sync(
                'zfs.dataset.query', [['id', '^', f'{os.path.join(k8s_config["dataset"], "releases")}/']], {
                    'extra': {'retrieve_properties': False}
                }
            )
        )
        for release_name in restored_chart_releases:
            new_mapping = self.middleware.call_sync(
                'chart.release.retrieve_pv_pvc_mapping_internal', chart_releases[release_name]
            )
            old_mapping = restored_chart_releases[release_name]['pv_info']
            # Do sanity checks now to see which datasets are present and hence can be restored to new mapping
            missing = collections.defaultdict(list)
            for mapping in (new_mapping, old_mapping):
                for pvc, ds in mapping.items():
                    if ds not in datasets:
                        missing[pvc].append(ds)

            failed = set()
            for pvc, new_ds in filter(lambda i: i[0] not in missing, new_mapping.items()):
                # Now we have assurance that dataset exists for new PV and old PV
                old_ds = old_mapping[pvc]
                try:
                    self.middleware.call_sync('zfs.dataset.delete', new_ds, {'force': True, 'recursive': True})
                except CallError:
                    failed.add(pvc)
                    self.logger.error('Failed to delete %r dataset', new_ds, exc_info=True)
                else:
                    try:
                        self.middleware.call_sync('zfs.dataset.rename', old_ds, {'new_name': new_ds})
                    except CallError:
                        self.logger.error('Failed to rename %r to %r dataset', old_ds, new_ds, exc_info=True)
                        failed.add(pvc)

            if missing or failed:
                error_str = f'Failed to restore PVC dataset(s) for {release_name!r}:\n'
                count = 1
                for m in missing:
                    error_str += f'{count}) {m} PVC (Unable to locate {", ".join(missing[m])} dataset(s))'
                    count += 1
                for f in failed:
                    error_str += f'{count}) {f} PVC (Unable to restore old PV dataset)'

                self.logger.error(error_str)

        job.set_progress(95, 'Scaling scalable workloads')

        for chart_release in restored_chart_releases.values():
            self.middleware.call_sync(
                'chart.release.scale_release_internal', chart_release['resources'], None,
                chart_release['replica_counts'], True,
            )

        self.middleware.call_sync(
            'k8s.node.remove_taints', [
                k['key'] for k in (self.middleware.call_sync('k8s.node.config')['spec']['taints'] or [])
                if k['key'] == 'ix-backup-restore'
            ]
        )

        job.set_progress(100, f'Restore of {backup_name!r} backup complete')
