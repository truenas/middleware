import errno
import os.path

from middlewared.api import api_method
from middlewared.api.current import (
    VirtVolumeEntry, VirtVolumeCreateArgs, VirtVolumeCreateResult, VirtVolumeUpdateArgs,
    VirtVolumeUpdateResult, VirtVolumeDeleteArgs, VirtVolumeDeleteResult, VirtVolumeImportISOArgs,
    VirtVolumeImportISOResult,
)
from middlewared.service import CallError, CRUDService, job, ValidationErrors
from middlewared.utils import filter_list

from .utils import incus_call, incus_call_sync, Status, incus_wait, storage_pool_to_incus_pool


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

        entries = []
        for storage_pool in config['storage_pools']:
            pool = storage_pool_to_incus_pool(storage_pool)
            storage_devices = await incus_call(f'1.0/storage-pools/{pool}/volumes/custom?recursion=2', 'get')
            if storage_devices.get('status_code') != 200:
                # This particular pool may not be available
                continue

            for storage_device in storage_devices['metadata']:
                entries.append({
                    'id': storage_device['name'],
                    'name': storage_device['name'],
                    'content_type': storage_device['content_type'].upper(),
                    'created_at': storage_device['created_at'],
                    'type': storage_device['type'],
                    'storage_pool': storage_pool,
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
        global_config = await self.middleware.call('virt.global.config')
        target_pool = global_config['pool'] if not data['storage_pool'] else data['storage_pool']

        verrors = ValidationErrors()
        ds_name = os.path.join(target_pool, f'.ix-virt/custom/default_{data["name"]}')
        if await self.middleware.call('virt.volume.query', [['id', '=', data['name']]]):
            verrors.add('virt_volume_create.name', 'Volume with this name already exists')
        elif await self.middleware.call(
            'zfs.dataset.query', [['id', '=', ds_name]], {
                'extra': {'retrieve_children': False, 'retrieve_properties': False}
            }
        ):
            # We will kick off recover here so that incus recognizes
            # this dataset as a volume already
            await self.middleware.call('virt.global.recover', [
                {
                    'config': {'source': f'{target_pool}/.ix-virt'},
                    'description': '',
                    'name': storage_pool_to_incus_pool(target_pool),
                    'driver': 'zfs',
                }
            ])
            verrors.add('virt_volume_create.name', 'ZFS dataset against this volume name already exists')

        if target_pool not in global_config['storage_pools']:
            verrors.add(
                'virt_volume_create.storage_pool',
                f'Not a valid storage pool. Choices are: {", ".join(global_config["storage_pools"])}'
            )

        verrors.check()

        incus_pool = storage_pool_to_incus_pool(target_pool)
        result = await incus_call(f'1.0/storage-pools/{incus_pool}/volumes/custom', 'post', {
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

        pool = storage_pool_to_incus_pool(volume['storage_pool'])
        result = await incus_call(f'1.0/storage-pools/{pool}/volumes/custom/{name}', 'patch', {
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

        pool = storage_pool_to_incus_pool(volume['storage_pool'])
        result = await incus_call(f'1.0/storage-pools/{pool}/volumes/custom/{name}', 'delete')
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
        global_config = await self.middleware.call('virt.global.config')
        target_pool = global_config['pool'] if not data['storage_pool'] else data['storage_pool']
        if target_pool not in global_config['storage_pools']:
            raise CallError('Not a valid storage pool')

        target_pool = storage_pool_to_incus_pool(target_pool)

        if data['upload_iso']:
            job.check_pipe('input')
        elif data['iso_location'] is None:
            raise CallError('Either upload iso or provide iso_location')

        if await self.middleware.call('virt.volume.query', [['id', '=', data['name']]]):
            raise CallError('Volume with this name already exists', errno=errno.EEXIST)

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
                    f'1.0/storage-pools/{target_pool}/volumes/custom',
                    'post',
                    request_kwargs=request_kwargs | {'data': read_input_stream()},
                )
            else:
                with open(data['iso_location'], 'rb') as f:
                    return incus_call_sync(
                        f'1.0/storage-pools/{target_pool}/volumes/custom',
                        'post',
                        request_kwargs=request_kwargs | {'data': f},
                    )

        response = await self.middleware.run_in_thread(upload_file)
        job.set_progress(70, 'ISO copied over to incus volume')
        await incus_wait(response)

        job.set_progress(95, 'ISO successfully imported as incus volume')
        return await self.get_instance(data['name'])
