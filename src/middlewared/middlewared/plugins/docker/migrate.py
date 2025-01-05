from datetime import datetime

from middlewared.service import CallError, private, Service

from .utils import applications_ds_name, MIGRATION_NAMING_SCHEMA


class DockerService(Service):

    @private
    async def migrate_ix_apps_dataset(self, job, config, old_config, migration_options):
        new_pool = config['pool']
        backup_name = f'backup_to_{new_pool}_{datetime.now().strftime("%F_%T")}'
        job.set_progress(30, 'Creating docker backup')
        backup_job = await self.middleware.call('docker.backup', backup_name)
        await backup_job.wait()
        if backup_job.error:
            raise CallError(f'Failed to backup docker apps: {backup_job.error}')

        try:
            job.set_progress(40, f'Replicating datasets from {old_config["pool"]!r} to {new_pool!r} pool')
            await self.replicate_apps_dataset(new_pool, old_config['pool'], migration_options)

            await self.middleware.call('datastore.update', 'services.docker', old_config['id'], config)

            job.set_progress(70, f'Restoring docker apps in {new_pool!r} pool')
            restore_job = await self.middleware.call('docker.restore_backup', backup_name)
            await restore_job.wait()
            if restore_job.error:
                raise CallError(f'Failed to restore docker apps on the new pool: {restore_job.error}')
        finally:
            await self.middleware.call('docker.delete_backup', backup_name)

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

        finally:
            await self.middleware.call('zfs.snapshot.delete', snap_details['id'], {'recursive': True})
            snap_name = f'{applications_ds_name(new_pool)}@{snap_details["snapshot_name"]}'
            if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
                await self.middleware.call('zfs.snapshot.delete', snap_name, {'recursive': True})
