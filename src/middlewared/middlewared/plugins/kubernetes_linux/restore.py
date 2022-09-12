import collections
import errno
import json
import os
import re
import shutil
import time
import yaml

from middlewared.schema import Dict, Bool, returns, Str
from middlewared.service import accepts, CallError, job, Service


RE_POOL = re.compile(r'^.*?(/.*)')


class KubernetesService(Service):

    @accepts(
        Str('backup_name'),
        Dict(
            'options',
            Bool('wait_for_csi', default=True),
        )
    )
    @returns()
    @job(lock='kubernetes_restore_backup')
    def restore_backup(self, job, backup_name, options):
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
        job.set_progress(15, 'Stopped kubernetes')

        shutil.rmtree('/etc/rancher', True)
        db_config = self.middleware.call_sync('datastore.config', 'services.kubernetes')
        self.middleware.call_sync('datastore.update', 'services.kubernetes', db_config['id'], {'cni_config': {}})

        k8s_config = self.middleware.call_sync('kubernetes.config')
        k8s_pool = k8s_config['pool']
        # We will be nuking the docker dataset and re-creating it
        # Motivation behind this action is that docker creates many datasets per image/container and
        # when we re-initialize the k8s cluster, it's possible we are leftover with datasets which are not
        # being used by any container. Images will be pulled again by k8s, so that shouldn't be a concern
        # in this regard.
        fresh_datasets = self.middleware.call_sync('kubernetes.to_ignore_datasets_on_backup', k8s_config['dataset'])
        for dataset in fresh_datasets:
            self.middleware.call_sync('zfs.dataset.delete', dataset, {'force': True, 'recursive': True})

        job.set_progress(20, f'Rolling back {backup["snapshot_name"]}')
        self.middleware.call_sync(
            'zfs.snapshot.rollback', backup['snapshot_name'], {
                'force': True,
                'recursive': True,
                'recursive_clones': True,
                'recursive_rollback': True,
            }
        )
        for dataset in fresh_datasets:
            self.middleware.call_sync('zfs.dataset.create', {'name': dataset, 'type': 'FILESYSTEM'})
            self.middleware.call_sync('zfs.dataset.mount', dataset)

        # FIXME: Remove this sleep, sometimes the k3s dataset fails to umount
        #  After discussion with mav, it sounds like a bug to him in zfs, so until that is fixed, we have this sleep
        # time.sleep(20)

        k3s_ds_path = os.path.join('/mnt', k8s_config['dataset'], 'k3s')
        # We are not deleting k3s ds simply because of upstream zfs bug (https://github.com/openzfs/zfs/issues/12460)
        # self.middleware.call_sync('zfs.dataset.delete', k3s_ds, {'force': True, 'recursive': True})
        # self.middleware.call_sync('zfs.dataset.create', {'name': k3s_ds, 'type': 'FILESYSTEM'})
        # self.middleware.call_sync('zfs.dataset.mount', k3s_ds)
        for name in os.listdir(k3s_ds_path):
            d_name = os.path.join(k3s_ds_path, name)
            if os.path.isdir(d_name):
                shutil.rmtree(d_name)

        job.set_progress(25, 'Initializing new kubernetes cluster')
        self.middleware.call_sync('service.start', 'kubernetes')

        while True:
            config = self.middleware.call_sync('k8s.node.config')
            if (
                config['node_configured'] and not config['spec']['taints'] and (
                    not options['wait_for_csi'] or self.middleware.call_sync('k8s.csi.config')['csi_ready']
                )
            ):
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

        # Now helm will recognise the releases as valid, however we don't have any actual k8s deployed resource
        # That will be adjusted with updating chart releases with their existing values and helm will see that
        # k8s resources don't exist and will create them for us
        job.set_progress(92, 'Creating kubernetes resources')
        update_jobs = []
        datasets = set(
            d['id'] for d in self.middleware.call_sync(
                'zfs.dataset.query', [['id', '^', f'{os.path.join(k8s_config["dataset"], "releases")}/']], {
                    'extra': {'retrieve_properties': False}
                }
            )
        )
        chart_releases_mapping = {c['name']: c for c in self.middleware.call_sync('chart.release.query')}
        for chart_release in restored_chart_releases:
            # Before we have resources created for the chart releases, we will restore PVs if possible and then
            # restore the chart release, so if there is any PVC expecting a PV, it will be able to claim it as soon
            # as it is created. If this is not done in this order, PVC will request a new dataset and we will lose
            # the mapping with the old dataset.
            self.middleware.call_sync(
                'chart.release.recreate_storage_class',
                chart_release, os.path.join(k8s_config['dataset'], 'releases', chart_release, 'volumes')
            )
            failed_pv_restores = []
            for pvc, pv in restored_chart_releases[chart_release]['pv_info'].items():
                pv['dataset'] = RE_POOL.sub(f'{k8s_pool}\\1', pv['dataset'])
                if pv['dataset'] not in datasets:
                    failed_pv_restores.append(f'Unable to locate PV dataset {pv["dataset"]!r} for {pvc!r} PVC.')
                    continue

                zv_details = pv['zv_details']
                try:
                    self.middleware.call_sync('k8s.zv.create', {
                        'metadata': {
                            'name': zv_details['metadata']['name'],
                        },
                        'spec': {
                            'capacity': zv_details['spec']['capacity'],
                            'poolName': RE_POOL.sub(f'{k8s_pool}\\1', zv_details['spec']['poolName']),
                        },
                    })
                except Exception as e:
                    failed_pv_restores.append(f'Unable to create ZFS Volume for {pvc!r} PVC: {e}')
                    continue

                pv_spec = pv['pv_details']['spec']
                try:
                    self.middleware.call_sync('k8s.pv.create', {
                        'metadata': {
                            'name': pv['name'],
                        },
                        'spec': {
                            'capacity': {
                                'storage': pv_spec['capacity']['storage'],
                            },
                            'claimRef': {
                                'name': pv_spec['claim_ref']['name'],
                                'namespace': pv_spec['claim_ref']['namespace'],
                            },
                            'csi': {
                                'volumeAttributes': {
                                    'openebs.io/poolname': RE_POOL.sub(
                                        f'{k8s_pool}\\1', pv_spec['csi']['volume_attributes']['openebs.io/poolname']
                                    )
                                },
                                'volumeHandle': pv_spec['csi']['volume_handle'],
                            },
                            'storageClassName': pv_spec['storage_class_name'],
                        },
                    })
                except Exception as e:
                    failed_pv_restores.append(f'Unable to create PV for {pvc!r} PVC: {e}')

            if failed_pv_restores:
                self.logger.error(
                    'Failed to restore PVC(s) for %r chart release:\n%s', chart_release, '\n'.join(failed_pv_restores)
                )

            release = chart_releases_mapping[chart_release]
            chart_path = os.path.join(release['path'], 'charts', release['chart_metadata']['version'])
            # We will create any relevant crds now if applicable
            crds_path = os.path.join(chart_path, 'crds')
            failed_crds = []
            if os.path.exists(crds_path):
                for crd_file in os.listdir(crds_path):
                    crd_path = os.path.join(crds_path, crd_file)
                    try:
                        self.middleware.call_sync('k8s.cluster.apply_yaml_file', crd_path)
                    except Exception as e:
                        failed_crds.append(f'Unable to create CRD(s) at {crd_path!r}: {e}')

            if failed_crds:
                self.logger.error(
                    'Failed to restore CRD(s) for %r chart release:\n%s', chart_release, '\n'.join(failed_crds)
                )

            update_jobs.append(self.middleware.call_sync('chart.release.redeploy_internal', chart_release, True))

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

        bulk_job = self.middleware.call_sync('kubernetes.redeploy_chart_releases_consuming_outdated_certs')
        for index, status in enumerate(bulk_job.wait_sync()):
            if status['error']:
                self.middleware.logger.error(
                    'Failed to redeploy %r chart release: %s', chart_releases[index], status['error']
                )

        job.set_progress(97, 'Scaling scalable workloads')

        for chart_release in restored_chart_releases.values():
            self.middleware.call_sync(
                'chart.release.scale_release_internal', chart_release['resources'], None,
                chart_release['replica_counts'], True,
            )

        job.set_progress(99, 'Syncing catalogs')
        sync_job = self.middleware.call_sync('catalog.sync_all')
        sync_job.wait_sync()
        if sync_job.error:
            self.logger.error('Failed to sync catalogs after restoring kubernetes backup')

        job.set_progress(100, f'Restore of {backup_name!r} backup complete')
