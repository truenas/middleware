import datetime
import errno
import os.path
from time import time

from middlewared.api import api_method
from middlewared.api.current import (
    VirtVolumeEntry, VirtVolumeCreateArgs, VirtVolumeCreateResult, VirtVolumeUpdateArgs,
    VirtVolumeUpdateResult, VirtVolumeDeleteArgs, VirtVolumeDeleteResult, VirtVolumeImportIsoArgs,
    VirtVolumeImportIsoResult, VirtVolumeImportZvolArgs, VirtVolumeImportZvolResult
)
from middlewared.plugins.zfs_.utils import zvol_path_to_name
from middlewared.service import CallError, CRUDService, job, ValidationErrors
from middlewared.utils import filter_list
from middlewared.utils.size import normalize_size

from .utils import incus_call, incus_call_sync, VirtGlobalStatus, incus_wait, storage_pool_to_incus_pool


class VirtVolumeService(CRUDService):

    class Config:
        namespace = 'virt.volume'
        cli_namespace = 'virt.volume'
        entry = VirtVolumeEntry
        role_prefix = 'VIRT_IMAGE'

    async def query(self, filters, options):
        config = await self.middleware.call('virt.global.config')
        if config['state'] != VirtGlobalStatus.INITIALIZED.value:
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
                    'id': f'{storage_pool}_{storage_device["name"]}',
                    'name': storage_device['name'],
                    'content_type': storage_device['content_type'].upper(),
                    'created_at': storage_device['created_at'],
                    'type': storage_device['type'],
                    'storage_pool': storage_pool,
                    'config': storage_device['config'],
                    'used_by': [instance.replace('/1.0/instances/', '') for instance in storage_device['used_by']]
                })
                if storage_device['config'].get('size'):
                    normalized_size = normalize_size(storage_device['config']['size'], False)
                    entries[-1]['config']['size'] = normalized_size // (1024 * 1024) if normalized_size else 0

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
            'zfs.resource.query_impl', {'paths': [ds_name], 'properties': None}
        ):
            # We will kick off recover here so that incus recognizes
            # this dataset as a volume already
            await (await self.middleware.call('virt.global.recover', [
                {
                    'config': {'source': f'{target_pool}/.ix-virt'},
                    'description': '',
                    'name': storage_pool_to_incus_pool(target_pool),
                    'driver': 'zfs',
                }
            ])).wait(raise_error=True)
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

        return await self.get_instance(f'{target_pool}_{data["name"]}')

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
        result = await incus_call(f'1.0/storage-pools/{pool}/volumes/custom/{volume["name"]}', 'patch', {
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
        result = await incus_call(f'1.0/storage-pools/{pool}/volumes/custom/{volume["name"]}', 'delete')
        if result.get('status_code') != 200:
            raise CallError(f'Failed to delete volume: {result["error"]}')

        return True

    @api_method(
        VirtVolumeImportIsoArgs,
        VirtVolumeImportIsoResult,
        audit='Virt: Importing',
        audit_extended=lambda data: f'{data["name"]!r} ISO',
        roles=['VIRT_IMAGE_WRITE']
    )
    @job(lock='virt_volume_import', pipes=['input'], check_pipes=False)
    async def import_iso(self, job, data):
        await self.middleware.call('virt.global.check_initialized')
        global_config = await self.middleware.call('virt.global.config')
        target_pool_ = global_config['pool'] if not data['storage_pool'] else data['storage_pool']
        if target_pool_ not in global_config['storage_pools']:
            raise CallError('Not a valid storage pool')

        target_pool = storage_pool_to_incus_pool(target_pool_)

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
            while True:
                chunk = job.pipes.input.r.read(1048576)
                if not chunk:
                    break

                yield chunk

        def upload_file():
            job.set_progress(25, 'Importing ISO as incus volume')
            if data['upload_iso']:
                return incus_call_sync(
                    f'1.0/storage-pools/{target_pool}/volumes/custom',
                    'post',
                    request_kwargs=request_kwargs | {'data': read_input_stream()},
                )
            else:
                try:
                    with open(data['iso_location'], 'rb') as f:
                        return incus_call_sync(
                            f'1.0/storage-pools/{target_pool}/volumes/custom',
                            'post',
                            request_kwargs=request_kwargs | {'data': f},
                        )
                except Exception as e:
                    raise CallError(f'Failed opening ISO: {e}')

        response = await self.middleware.run_in_thread(upload_file)
        job.set_progress(70, 'ISO copied over to incus volume')
        await incus_wait(response)

        job.set_progress(95, 'ISO successfully imported as incus volume')
        return await self.get_instance(f'{target_pool_}_{data["name"]}')

    @api_method(
        VirtVolumeImportZvolArgs,
        VirtVolumeImportZvolResult,
        audit='Virt: Importing',
        audit_extended=lambda data: f'{data["name"]!r} zvol',
        roles=['VIRT_IMAGE_WRITE']
    )
    @job(lock='virt_volume_import')
    async def import_zvol(self, job, data):
        await self.middleware.call('virt.global.check_initialized')
        global_config = await self.middleware.call('virt.global.config')
        zvol_choices = set([
            x for x in (await self.middleware.call('virt.device.disk_choices')).keys() if x.startswith('/dev')
        ])
        pools = set()

        verrors = ValidationErrors()
        if len(data['to_import']) == 0:
            verrors.add('virt_volume_import_zvol.import', 'At least one entry is required.')

        for idx, entry in enumerate(data['to_import']):
            entry['zvol_name'] = zvol_path_to_name(entry['zvol_path'])
            entry['zpool'] = entry['zvol_name'].split('/')[0]
            entry['new_name'] = f'{entry["zpool"]}/.ix-virt/custom/default_{entry["virt_volume_name"]}'
            if entry['zpool'] not in global_config['storage_pools']:
                verrors.add(
                    f'virt_volume_import_zvol.import.{idx}.entry.zvol_path',
                    f'{entry["zpool"]}: zvol is not located in pool configured '
                    'as a virt storage pool.'
                )
            elif entry['zvol_path'] not in zvol_choices:
                verrors.add(
                    f'virt_volume_import_zvol.import.{idx}.entry.zvol_path',
                    f'{entry["zvol_path"]}: not an available zvol choice.'
                )

            else:
                pools.add(entry['zpool'])

                # The ZFS rename will break snapshot task attachments
                # and so user will need to remove any snapshot tasks
                attachments = await self.middleware.call('pool.dataset.attachments', entry['zvol_name'])
                if attachments:
                    attachment_types = [x['type'] for x in attachments]
                    verrors.add(
                        f'virt_volume_import_zvol.import.{idx}.entry.zvol_name',
                        f'{entry["zvol_name"]}: specified zvol is currently in use: {", ".join(attachment_types)}'
                    )

        verrors.check()

        job.set_progress(5, 'Preparing to rename zvols')

        # Revert dataset operations on failure
        # each entry will be tuple of method name and args for API call to revert the previous action
        revert = []
        for entry in data['to_import']:
            orig_name = entry['zvol_name']
            new_name = entry['new_name']
            now = int(time())  # use unix timestamp to reduce character count
            snap_name = f'incus_{now}'
            full_snap = f'{orig_name}@{snap_name}'

            try:
                if data['clone']:
                    job.set_progress(description=f'Cloning {orig_name} to {new_name}')
                    await self.middleware.call('zfs.snapshot.create', {'dataset': orig_name, 'name': snap_name})
                    revert.append(('zfs.snapshot.delete', [full_snap]))

                    await self.middleware.call('zfs.snapshot.clone', {'snapshot': full_snap, 'dataset_dst': new_name})
                    revert.append(('zfs.dataset.delete', [new_name]))

                    await self.middleware.call('zfs.dataset.promote', new_name)
                    revert.append(('zfs.dataset.promote', [orig_name]))
                else:
                    job.set_progress(description=f'Renaming {orig_name} to {new_name}')
                    await self.middleware.call('zfs.dataset.rename', orig_name, {'new_name': new_name})
                    revert.append(('zfs.dataset.rename', [new_name, {'new_name': orig_name}]))

                await self.middleware.call('zfs.dataset.update', new_name, {"properties": {
                    'incus:content_type': {'value': 'block'},
                }})
                ds = await self.middleware.call(
                    'zfs.resource.query_impl',
                    {'paths': [new_name], 'properties': ['volsize', 'creation']}
                )[0]['properties']
                entry['volsize'] = ds['volsize']['value']
                entry['creation'] = ds['creation']['value']
            except Exception:
                self.logger.error('%s: failed to import zvol', orig_name, exc_info=True)

                job.set_progress(description='Reverting changes')
                for action in reversed(revert):
                    method, args = action
                    await self.middleware.call(method, *args)

                raise

        recover_payload = []

        # We need to trigger a recovery action from incus to get the volumes
        # inserted into the incus database and recovery files
        for pool in pools:
            incus_pool = storage_pool_to_incus_pool(pool)
            recover_payload.append({
                'config': {'source': f'{pool}/.ix-virt'},
                'description': '',
                'name': incus_pool,
                'driver': 'zfs',
            })

        # If this fails, our state cannot be cleanly rolled back.
        # admin will need to toggle virt.global enabled state
        job.set_progress(50, 'Updating backend database')
        await (await self.middleware.call('virt.global.recover', recover_payload)).wait(raise_error=True)

        # At this point the zvols have been renamed and incus DB updated
        # but we still need to fix some volume-related metadata. The size
        # of the volume and the create time of the volume are not properly
        # set by the incus ZFS driver
        job.set_progress(50, 'Updating volume metadata')

        for entry in data['to_import']:
            pool = storage_pool_to_incus_pool(entry['zpool'])
            name = entry['virt_volume_name']

            result = await incus_call(f'1.0/storage-pools/{pool}/volumes/custom/{name}', 'patch', {
                'json': {
                    'config': {
                        'size': str(entry['volsize']),
                    },
                    'created_at': datetime.datetime.fromtimestamp(
                        entry['creation'], datetime.UTC
                    ).isoformat()
                },
            })
            if result.get('error') != '':
                raise CallError(f'Failed to update volume: {result["error"]}')
