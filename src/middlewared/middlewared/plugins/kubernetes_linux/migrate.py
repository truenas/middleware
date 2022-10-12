import glob
import os
import yaml

from datetime import datetime

from middlewared.service import CallError, private, Service

from .utils import applications_ds_name, MIGRATION_NAMING_SCHEMA


class KubernetesService(Service):

    @private
    async def migrate_ix_applications_dataset(self, job, config, old_config, migration_options):
        new_pool = config['pool']
        backup_name = f'backup_to_{new_pool}_{datetime.utcnow().strftime("%F_%T")}'
        job.set_progress(30, 'Creating kubernetes cluster backup')
        backup_job = await self.middleware.call('kubernetes.backup_chart_releases', backup_name)
        await backup_job.wait()
        if backup_job.error:
            raise CallError(f'Failed to backup kubernetes cluster: {backup_job.error}')

        try:
            job.set_progress(40, f'Replicating datasets from {old_config["pool"]!r} to {new_pool!r} pool')
            await self.replicate_apps_dataset(new_pool, old_config['pool'], migration_options)

            await self.middleware.call('datastore.update', 'services.kubernetes', old_config['id'], config)

            job.set_progress(70, f'Restoring kubernetes cluster in {new_pool!r} pool')
            restore_job = await self.middleware.call('kubernetes.restore_backup', backup_name)
            await restore_job.wait()
            if restore_job.error:
                raise CallError(f'Failed to restore kubernetes cluster on the new pool: {restore_job.error}')
        finally:
            await self.middleware.call('kubernetes.delete_backup', backup_name)

    @private
    async def replicate_apps_dataset(self, new_pool, old_pool, migration_options):
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

            await self.handle_encrypted_ix_apps_dataset(new_pool, old_pool, migration_options)
        finally:
            await self.middleware.call('zfs.snapshot.delete', snap_details['id'], {'recursive': True})
            snap_name = f'{applications_ds_name(new_pool)}@{snap_details["snapshot_name"]}'
            if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
                await self.middleware.call('zfs.snapshot.delete', snap_name, {'recursive': True})

    @private
    async def handle_encrypted_ix_apps_dataset(self, new_pool, old_pool, migration_options):
        # If new-pool/ix-apps is encrypted here, it means that old-pool is encrypted and we want
        # to unlock new-pool/ix-apps and have it inherit new-pool properties
        new_apps_ds = await self.middleware.call(
            'zfs.dataset.query', [['id', '=', applications_ds_name(new_pool['pool'])]], {
                'extra': {'retrieve_children': False, 'retrieve_properties': True},
                'get': True,
            }
        )
        if not new_apps_ds['encrypted']:
            return

        if not new_apps_ds['locked']:
            # This is a sanity check
            raise CallError(f'{new_apps_ds["id"]!r} must be locked after replicating from source pool')

        # We will rename apps dataset as ix-applications is filtered out by pool.dataset.query
        # and we won't be able to unlock it in this manner
        new_name = os.path.join(new_pool, 'ix-applications-migration_enc_temp')
        await self.middleware.call('zfs.dataset.rename', new_apps_ds['id'], {'new_name': new_name})

        unlock_options = {
            'passphrase': migration_options['passphrase'],
        } if new_apps_ds['key_format']['value'] == 'PASSPHRASE' else {
            'key': (await self.middleware.call(
                'datastore.query', 'storage.encrypteddataset', [['name', '=', old_pool]]
            ))['encryption_key']
        }

        unlock_job = await self.middleware.call('pool.dataset.unlock', new_name, {
            'datasets': [{
                'name': new_name,
                'recursive': True,
                **unlock_options,
            }]
        })
        await unlock_job.wait()
        if unlock_job.error:
            raise CallError(f'Failed to unlock migrated ix-applications dataset: {unlock_job.error!r}')

        await self.middleware.call('pool.dataset.inherit_parent_encryption_properties', new_name)
        await self.middleware.call('zfs.dataset.rename', new_name, {'new_name': new_name})

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
