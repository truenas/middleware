import os
from datetime import datetime

from middlewared.service import CallError, private, Service
from middlewared.service_exception import InstanceNotFound
from middlewared.plugins.pool_.utils import CreateImplArgs
from middlewared.plugins.zfs.destroy_impl import DestroyArgs

from .state_utils import DatasetDefaults, Status
from .utils import applications_ds_name, MIGRATION_NAMING_SCHEMA


class DockerService(Service):

    @private
    async def migrate_ix_apps_dataset(self, job, config, old_config, migration_options):
        new_pool = config['pool']
        backup_name = f'backup_to_{new_pool}_{datetime.now().strftime("%F_%T")}'
        await self.middleware.call('docker.state.set_status', Status.MIGRATING.value)
        job.set_progress(30, 'Creating docker backup')
        backup_job = await self.middleware.call('docker.backup', backup_name)
        await backup_job.wait()
        if backup_job.error:
            raise CallError(f'Failed to backup docker apps: {backup_job.error}')

        job.set_progress(35, 'Stopping docker service')
        await (await self.middleware.call('service.control', 'STOP', 'docker')).wait(raise_error=True)

        try:
            job.set_progress(40, f'Replicating datasets from {old_config["pool"]!r} to {new_pool!r} pool')
            dsname = applications_ds_name(config['pool'])
            await self.middleware.call(
                'pool.dataset.create_impl',
                CreateImplArgs(
                    name=dsname,
                    ztype='FILESYSTEM',
                    zprops=DatasetDefaults.create_time_props(os.path.basename(dsname))
                )
            )
            await (await self.middleware.call('docker.fs_manage.umount')).wait()

            await self.replicate_apps_dataset(new_pool, old_config['pool'], migration_options)

            await self.middleware.call('datastore.update', 'services.docker', old_config['id'], config)

            job.set_progress(70, f'Restoring docker apps in {new_pool!r} pool')
            restore_job = await self.middleware.call('docker.restore_backup', backup_name)
            await restore_job.wait()
            if restore_job.error:
                raise CallError(f'Failed to restore docker apps on the new pool: {restore_job.error}')
        except Exception:
            await self.middleware.call('docker.state.set_status', Status.MIGRATION_FAILED.value)
            raise
        else:
            job.set_progress(100, 'Migration completed successfully')
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
                    'retention_policy': 'SOURCE',
                    'replicate': True,
                    'readonly': 'IGNORE',
                    'exclude_mountpoint_property': False,
                }
            )
            await migrate_job.wait()
            if migrate_job.error:
                raise CallError(f'Failed to migrate {old_ds} to {new_ds}: {migrate_job.error}')

        finally:
            await self.middleware.call(
                'zfs.resource.destroy', DestroyArgs(path=snap_details['id'], recursive=True)
            )
            snap_name = f'{applications_ds_name(new_pool)}@{snap_details["snapshot_name"]}'
            try:
                await self.middleware.call(
                    'zfs.resource.destroy', DestroyArgs(path=snap_name, recursive=True)
                )
            except InstanceNotFound:
                pass
