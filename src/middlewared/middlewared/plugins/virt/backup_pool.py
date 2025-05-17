from middlewared.api import api_method
from middlewared.api.current import (
    VirtBackupStoragePoolArgs, VirtBackupStoragePoolResult,
)
from middlewared.service import CallError, job, private, Service, ValidationErrors

from .backup_utils import (
    get_containers_parent_ds, get_vms_parent_ds, MIGRATION_NAMING_SCHEMA, normalize_instances, virt_ds_name,
)


class VirtBackupService(Service):

    class Config:
        namespace = 'virt.backup'

    @api_method(VirtBackupStoragePoolArgs, VirtBackupStoragePoolResult, roles=['VIRT_INSTANCE_WRITE'])
    @job(lock='virt_backup_storage_pool')
    async def storage_pool(self, job, data):
        await self.middleware.call('virt.global.check_initialized')
        verrors = ValidationErrors()
        pool = data['incus_storage_pool']
        target_pool = data['target_pool']
        config = await self.middleware.call('virt.global.config')
        if pool not in config['storage_pools']:
            verrors.add(
                'virt_backup_storage_pool.incus_storage_pool',
                f'Storage pool {pool} not found in the list of storage pools'
            )
        if target_pool in config['storage_pools']:
            verrors.add(
                'virt_backup_storage_pool.target_pool',
                'Target pool must not already be selected as an incus storage pool'
            )

        verrors.check()

        job.set_progress(10, 'Initial validation complete')
        # Game plan here is the following:
        # 1) Replicate ix-virt dataset to target pool
        # 2) Once it is in place, make sure we go over each instance and remove any pool specific bits
        # 3) This should be ensured for containers/vms/volumes
        # It seems there is nothing to be done for volumes
        # TODO: Make sure above assumption is accurate

        # FIXME: Handle incremental backup

        job.set_progress(20, f'Migrating virt state from {pool!r} to {target_pool!r}')
        await self.replicate_dataset(target_pool, pool)
        job.set_progress(70, f'Normalizing virt state in {target_pool!r} pool')
        instances = []
        containers = await self.middleware.call(
            'zfs.dataset.query', [['id', '=', get_containers_parent_ds(target_pool)]], {
                'extra': {'flat': False, 'retrieve_properties': False}
            }
        )
        if containers:
            instances.extend(containers[0]['children'])
        vms = await self.middleware.call(
            'zfs.dataset.query', [['id', '=', get_vms_parent_ds(target_pool)]], {
                'extra': {'flat': False, 'retrieve_properties': False}
            }
        )
        if vms:
            instances.extend(vms[0]['children'])

        await self.middleware.run_in_thread(normalize_instances, pool, target_pool, instances)

        job.set_progress(100, f'Backup of {pool!r} to {target_pool!r} complete')
        return True

    @private
    async def replicate_dataset(self, new_pool, old_pool):
        snap_details = await self.middleware.call(
            'zfs.snapshot.create', {
                'dataset': virt_ds_name(old_pool),
                'naming_schema': MIGRATION_NAMING_SCHEMA,
                'recursive': True,
            }
        )

        try:
            old_ds = virt_ds_name(old_pool)
            new_ds = virt_ds_name(new_pool)
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
            await self.middleware.call('zfs.snapshot.delete', snap_details['id'], {'recursive': True})
            snap_name = f'{virt_ds_name(new_pool)}@{snap_details["snapshot_name"]}'
            if await self.middleware.call('zfs.snapshot.query', [['id', '=', snap_name]]):
                await self.middleware.call('zfs.snapshot.delete', snap_name, {'recursive': True})
