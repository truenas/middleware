import os
import uuid

from middlewared.api import api_method
from middlewared.api.v25_10_0 import VirtBackupExportArgs, VirtBackupExportResult
from middlewared.service import job, private, Service, ValidationErrors

from .utils import incus_call_and_wait, read_from_incus_stream_and_write_to_file, storage_pool_to_incus_pool


class VirtBackupService(Service):

    class Config:
        namespace = 'virt.backup'
        cli_namespace = 'virt.backup'

    @api_method(
        VirtBackupExportArgs,
        VirtBackupExportResult,
        audit='Virt: Backup',
        audit_extended=lambda data: f'{data["instance_name"]!r} Backup',
        roles=['VIRT_INSTANCE_WRITE'],
    )
    @job(lock='virt_backup_export')
    async def export(self, job, data):
        await self.middleware.call('virt.global.check_initialized')
        verrors = ValidationErrors()
        global_config = await self.middleware.call('virt.global.config')
        if not global_config['export_dir']:
            verrors.add('virt_backup.backup_name', 'Export directory must be set in virt global configuration')

        verrors.check()

        await self.middleware.run_in_thread(os.makedirs, global_config['export_dir'], exist_ok=True)

        resource_type = 'instance' if data['resource_type'] == 'INSTANCE' else 'volume'
        resource_data = await self.middleware.call(f'virt.{resource_type}.query', [['id', '=', data['resource_name']]])
        if not resource_data:
            verrors.add(
                'virt_backup.resource_name', f'{data["resource_type"]} {data["resource_name"]!r} does not exist'
            )
        else:
            resource_data = resource_data[0]

        export_path = os.path.join(global_config['export_dir'], data['backup_name'])
        if await self.middleware.run_in_thread(os.path.exists, export_path):
            verrors.add('virt_backup.backup_name', f'Backup {export_path!r} already exists')

        if resource_type == 'volume' and resource_data['content_type'] == 'ISO':
            verrors.add('virt_backup.resource_name', 'Volume with content type of ISO cannot be exported')

        verrors.check()

        if resource_type == 'instance' and data['backup_instance_volumes'] and resource_data['type'] == 'VM':
            volume_mapping = {v['id']: v for v in await self.middleware.call('virt.volume.query')}
            volumes = []
            for device in filter(
                lambda d: d['dev_type'] == 'DISK' and d['source'],
                await self.middleware.call('virt.instance.device_list', data['resource_name'])
            ):
                if volume_mapping.get(device['source'], {}).get('content_type', 'ISO') != 'ISO':
                    volumes.append(device['source'])

            if volumes:
                # We have volumes along with the instance which are to be backed up as well
                await self.middleware.run_in_thread(os.makedirs, export_path)
                await self.backup_impl(
                    job, data, resource_data, os.path.join(export_path, 'root'), 0, 60
                )
                len_volumes = len(volumes)
                for index, volume in enumerate(volumes):
                    volume = volume_mapping[volume]
                    start = 60 + (index * 35 / len_volumes)
                    end = 60 + ((index + 1) * 35 / len_volumes)
                    await self.backup_impl(
                        job, {
                            'resource_name': volume['name'],
                            'resource_type': 'VOLUME',
                        }, volume, os.path.join(export_path, f'volume_{volume["id"]}'), start, end
                    )
            else:
                await self.backup_impl(job, data, resource_data, export_path)
        else:
            await self.backup_impl(job, data, resource_data, export_path)

        job.set_progress(100, f'Backup exported successfully to {export_path}')
        return export_path

    @private
    async def backup_impl(self, job, data, resource_data, export_path, base_percentage=0, max_percentage=100):
        backup_name = f'backup-{data["resource_name"]}-{str(uuid.uuid4())[:4]}'
        rsrc_name = data['resource_name']
        if data['resource_type'] == 'INSTANCE':
            backup_url = f'1.0/instances/{rsrc_name}/backups'
            export_url = f'1.0/instances/{rsrc_name}/backups/{backup_name}/export'
            backup_del_url = f'1.0/instances/{rsrc_name}/backups/{backup_name}'
        else:
            pool_name = storage_pool_to_incus_pool(resource_data['storage_pool'])
            backup_url = f'1.0/storage-pools/{pool_name}/volumes/custom/{rsrc_name}/backups'
            export_url = f'1.0/storage-pools/{pool_name}/volumes/custom/{rsrc_name}/backups/{backup_name}/export'
            backup_del_url = f'1.0/storage-pools/{pool_name}/volumes/custom/{rsrc_name}/backups/{backup_name}'

        job.set_progress(base_percentage + (0.1 * (max_percentage-base_percentage)), 'Generating backup')
        await incus_call_and_wait(
            backup_url, 'post', request_kwargs={'json': {
                'name': backup_name, 'compression_algorithm': 'gzip', 'optimized-storage': 'zfs'
            }}
        )
        try:
            job.set_progress(base_percentage + (0.65 * (max_percentage-base_percentage)), 'Exporting backup')
            await self.middleware.run_in_thread(read_from_incus_stream_and_write_to_file, export_url, export_path)
        finally:
            job.set_progress(base_percentage + (0.85 * (max_percentage-base_percentage)), 'Cleaning up')
            await incus_call_and_wait(backup_del_url, 'delete')
