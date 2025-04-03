import os

from middlewared.api import api_method
from middlewared.api.v25_10_0 import VirtBackupImportArgs, VirtBackupImportResult
from middlewared.service import job, private, Service, ValidationErrors

from .utils import incus_wait, storage_pool_to_incus_pool, write_to_incus_stream


class VirtBackupService(Service):

    class Config:
        namespace = 'virt.backup'
        cli_namespace = 'virt.backup'

    @api_method(
        VirtBackupImportArgs,
        VirtBackupImportResult,
        audit='Virt: Importing',
        audit_extended=lambda data: f'{data["name"]!r} importing',
        roles=['VIRT_INSTANCE_WRITE'],
    )
    @job(lock='virt_backup_import')
    def apply(self, job, data):
        self.middleware.call_sync('virt.global.check_initialized')
        verrors = ValidationErrors()
        global_config = self.middleware.call_sync('virt.global.config')
        resource_type = 'instance' if data['resource_type'] == 'INSTANCE' else 'volume'
        target_pool = data['storage_pool'] or global_config['pool']
        if target_pool not in global_config['storage_pools']:
            verrors.add('virt_backup_import.storage_pool', f'Storage pool is not configured in virt storage pools')

        if self.middleware.call_sync(f'virt.{resource_type}.query', [['name', '=', data['resource_name']]]):
            verrors.add(
                'virt_backup_import.resource_name',
                f'{data["resource_type"]} with {data["resource_name"]!r} already exists'
            )

        if os.path.exists(data['backup_location']) is False:
            verrors.add(
                'virt_backup_import.backup_location', f'Backup {data["backup_location"]!r} path does not exist'
            )

        verrors.check()

        # If backup path is a directory, it means likely that we have a complete instance backed up with
        # root disk + config and volumes. In this case, we would like to restore volumes first and then the root disk
        # and VM
        to_restore_dir = []
        if os.path.isdir(data['backup_location']):
            found_root = False
            with os.scandir(data['backup_location']) as sdir:
                for filename in map(lambda f: f.name, sdir):
                    if filename == 'root' and os.path.isfile(os.path.join(data['backup_location'], filename)):
                        found_root = True
                    elif filename.startswith(
                        'volume_') and os.path.isfile(os.path.join(data['backup_location'], filename)
                    ):
                        to_restore_dir.append(os.path.join(data['backup_location'], filename))

            if found_root is False:
                verrors.add(
                    'virt_backup_import.backup_location',
                    'Backup directory does not contain root disk file'
                )
            else:
                # We want to add root disk at the end so that we can restore volumes first
                to_restore_dir.append(os.path.join(data['backup_location'], 'root'))

        verrors.check()

        job.set_progress(10, 'Completed initial validation')
        if to_restore_dir:
            restore_items_len = len(to_restore_dir)
            for index, item in enumerate(to_restore_dir):
                name = os.path.basename(item)
                rsrc_name = data['resource_name'] if name == 'root' else name.removeprefix('volume_')
                start = (index * 100) / restore_items_len
                end = ((index + 1) * 100) / restore_items_len
                self.middleware.call_sync(
                    'virt.backup.import_impl', job, {
                        'resource_name': rsrc_name,
                        'resource_type': 'INSTANCE' if name == 'root' else 'VOLUME',
                        'backup_location': item,
                    }, target_pool, start, end
                )
        else:
            self.middleware.call_sync(
                'virt.backup.import_impl', job, data | {'backup_location': data['backup_location']}, target_pool
            )

        job.set_progress(100, 'Completed importing backup')
        return self.middleware.call_sync(f'virt.{resource_type}.get_instance', data['resource_name'])

    @private
    async def import_impl(self, job, data, target_pool, base_percentage=0, max_percentage=100):
        request_kwargs = {
            'headers': {
                'X-Incus-name': data['resource_name'],
                'Content-Type': 'application/octet-stream',
            },
        }
        incus_target_pool = storage_pool_to_incus_pool(target_pool)
        if data['resource_type'] == 'INSTANCE':
            import_url = '1.0/instances'
            req_extra_args = {'X-Incus-pool': incus_target_pool}
        else:
            import_url = f'1.0/storage-pools/{incus_target_pool}/volumes/custom'
            req_extra_args = {'X-Incus-type': 'block'}

        request_kwargs['headers'] |= req_extra_args
        job.set_progress(base_percentage + (0.25 * (max_percentage - base_percentage)),
                         'Importing backup into the incus')

        response = await self.middleware.run_in_thread(
            write_to_incus_stream, import_url, request_kwargs, data['backup_location']
        )
        await incus_wait(response)
