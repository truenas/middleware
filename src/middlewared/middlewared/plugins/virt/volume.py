import errno

from middlewared.api import api_method
from middlewared.api.current import (
    VirtVolumeEntry, VirtVolumeCreateArgs, VirtVolumeCreateResult, VirtVolumeUpdateArgs,
    VirtVolumeUpdateResult, VirtVolumeDeleteArgs, VirtVolumeDeleteResult, VirtVolumeImportISOArgs,
    VirtVolumeImportISOResult,
)
from middlewared.service_exception import ValidationError, ValidationErrors
from middlewared.service import CallError, CRUDService, job
from middlewared.utils import filter_list

from .utils import incus_call, incus_call_sync, Status, incus_wait


class VirtVolumeService(CRUDService):

    class Config:
        namespace = 'virt.volume'
        cli_namespace = 'virt.volume'
        entry = VirtVolumeEntry
        role_prefix = 'VIRT_IMAGE'

    async def query(self, filters, options):
        config = await self.middleware.call('virt.global.config')
        if config['state'] != Status.INITIALIZED.value:
            return []

        storage_devices = await incus_call('1.0/storage-pools/default/volumes/custom?recursion=2', 'get')
        if storage_devices.get('status_code') != 200:
            return []

        entries = []
        for storage_device in storage_devices['metadata']:
            entries.append({
                'id': storage_device['name'],
                'name': storage_device['name'],
                'content_type': storage_device['content_type'].upper(),
                'created_at': storage_device['created_at'],
                'type': storage_device['type'],
                'config': storage_device['config'],
                'used_by': [instance.replace('/1.0/instances/', '') for instance in storage_device['used_by']]
            })
            if storage_device['config'].get('size'):
                entries[-1]['config']['size'] = int(storage_device['config']['size']) // (1024 * 1024)
        return filter_list(entries, filters, options)

    @api_method(
        VirtVolumeCreateArgs,
        VirtVolumeCreateResult,
        audit='Virt: Creating',
        audit_extended=lambda data: f'{data["name"]!r} volume'
    )
    async def do_create(self, data):
        await self.middleware.call('virt.global.check_initialized')

        verrors = ValidationErrors()
        if await self.middleware.call('virt.volume.query', [['id', '=', data['name']]]):
            verrors.add('virt_volume_create.name', 'Volume with this name already exists')
        verrors.check()

        result = await incus_call('1.0/storage-pools/default/volumes/custom', 'post', {
            'json': {
                'name': data['name'],
                'content_type': data['content_type'].lower(),
                'config': {
                    'size': str(data['size'] * 1024 * 1024),  # Convert MB to bytes
                },
            },
        })
        if result.get('error') != '':
            raise CallError(f'Failed to create volume: {result["error"]}')

        return await self.get_instance(data['name'])

    @api_method(
        VirtVolumeUpdateArgs,
        VirtVolumeUpdateResult,
        audit='Virt: Updating',
        audit_extended=lambda name, data=None: f'{name!r} volume'
    )
    async def do_update(self, name, data):
        volume = await self.get_instance(name)
        if data.get('size') is None:
            return volume

        result = await incus_call(f'1.0/storage-pools/default/volumes/custom/{name}', 'patch', {
            'json': {
                'config': {
                    'size': str(data['size'] * 1024 * 1024)
                },
            },
        })
        if result.get('error') != '':
            raise CallError(f'Failed to update volume: {result["error"]}')

        return await self.get_instance(name)

    @api_method(
        VirtVolumeDeleteArgs,
        VirtVolumeDeleteResult,
        audit='Virt: Deleting',
        audit_extended=lambda name: f'{name!r} volume'
    )
    async def do_delete(self, name):
        volume = await self.get_instance(name)
        if volume['used_by']:
            raise CallError(f'Volume {name!r} is in use by instances: {", ".join(volume["used_by"])}')

        result = await incus_call(f'1.0/storage-pools/default/volumes/custom/{name}', 'delete')
        if result.get('status_code') != 200:
            raise CallError(f'Failed to delete volume: {result["error"]}')

        return True

    @api_method(
        VirtVolumeImportISOArgs,
        VirtVolumeImportISOResult,
        audit='Virt: Importing',
        audit_extended=lambda data: f'{data["name"]!r} ISO',
        roles=['VIRT_IMAGE_WRITE']
    )
    @job(lock=lambda args: f'virt_volume_import_iso_{args[0]}', pipes=['input'], check_pipes=False)
    async def import_iso(self, job, data):
        await self.middleware.call('virt.global.check_initialized')

        if data['upload_iso']:
            job.check_pipe('input')
        elif data['iso_location'] is None:
            raise ValidationError(
                'virt_volume_import_iso.iso_location',
                'Either upload iso or provide iso_location'
            )

        if await self.middleware.call('virt.volume.query', [['id', '=', data['name']]]):
            raise ValidationError(
                'virt_volume_import_iso.name',
                'Volume with this name already exists',
                errno=errno.EEXIST
            )

        request_kwargs = {
            'headers': {
                'X-Incus-type': 'iso',
                'X-Incus-name': data['name'],
                'Content-Type': 'application/octet-stream',
            }
        }

        def read_input_stream():
            for stream in job.pipes.input.r:
                yield stream

        def upload_file():
            job.set_progress(25, 'Importing ISO as incus volume')
            if data['upload_iso']:
                return incus_call_sync(
                    '1.0/storage-pools/default/volumes/custom',
                    'post',
                    request_kwargs=request_kwargs | {'data': read_input_stream()},
                )
            else:
                try:
                    with open(data['iso_location'], 'rb') as f:
                        return incus_call_sync(
                            '1.0/storage-pools/default/volumes/custom',
                            'post',
                            request_kwargs=request_kwargs | {'data': f},
                        )
                except FileNotFoundError:
                    raise ValidationError(
                        'virt_volume_import_iso.iso_location',
                        f'{data["iso_location"]!r} does not exist'
                    )

        response = await self.middleware.run_in_thread(upload_file)
        job.set_progress(70, 'ISO copied over to incus volume')
        await incus_wait(response)

        job.set_progress(95, 'ISO successfully imported as incus volume')
        return await self.get_instance(data['name'])
