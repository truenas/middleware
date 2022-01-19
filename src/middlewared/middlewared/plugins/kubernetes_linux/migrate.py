import glob
import os
import yaml

from middlewared.service import CallError, private, Service

from .utils import applications_ds_name, MIGRATION_NAMING_SCHEMA


class KubernetesService(Service):

    @private
    async def migrate_ix_applications_dataset(self, new_pool, old_pool):
        snap_details = await self.middleware.call(
            'zfs.snapshot.create', {
                'dataset': applications_ds_name(old_pool),
                'naming_schema': MIGRATION_NAMING_SCHEMA,
                'recursive': True,
            }
        )

        try:
            old_ds = applications_ds_name(old_pool)
            new_ds = applications_ds_name(new_pool)
            migrate_job = await self.middleware.call(
                'replication.run_onetime', {
                    'direction': 'PUSH',
                    'transport': 'LOCAL',
                    'source_datasets': [old_ds],
                    'target_dataset': new_ds,
                    'recursive': True,
                    'also_include_naming_schema': [MIGRATION_NAMING_SCHEMA],
                    'retention_policy': 'NONE',
                    'replicate': True,
                    'readonly': 'IGNORE',
                    'exclude_mountpoint_property': False,
                }
            )
            await migrate_job.wait()
            if migrate_job.error:
                raise CallError(f'Failed to migrate {old_ds} to {new_ds}: {migrate_job.error}')

            # We will make sure that certificate paths point to the newly configured pool
            await self.middleware.call('kubernetes.update_server_credentials', new_ds)
        finally:
            await self.middleware.call('zfs.snapshot.delete', snap_details['id'], {'recursive': True})
            snap_name = f'{applications_ds_name(new_pool)}@{snap_details["snapshot_name"]}'
            if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
                await self.middleware.call('zfs.snapshot.delete', snap_name, {'recursive': True})

    @private
    def update_server_credentials(self, apps_dataset):
        server_folder = os.path.join('/mnt', apps_dataset, 'k3s/server')
        creds_folder = os.path.join(server_folder, 'cred')
        for kubeconfig_path in glob.glob(f'{creds_folder}/*kubeconfig'):
            with open(kubeconfig_path, 'r') as f:
                kubeconfig = yaml.safe_load(f.read())

            for cluster_info in filter(
                lambda d: 'cluster' in d and 'certificate-authority' in d['cluster'], kubeconfig['clusters']
            ):
                cluster_info['cluster']['certificate-authority'] = os.path.join(server_folder, 'tls/server-ca.crt')

            for user_info in filter(
                lambda d: 'user' in d and all(k in d['user'] for k in ('client-certificate', 'client-key')),
                kubeconfig['users']
            ):
                for k in ('client-certificate', 'client-key'):
                    path = user_info['user'][k].rsplit('ix-applications/k3s/server/', 1)[-1]
                    user_info['user'][k] = os.path.join(server_folder, path)

            with open(kubeconfig_path, 'w') as f:
                f.write(yaml.safe_dump(kubeconfig))
