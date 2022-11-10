import collections
import contextlib
import glob
import os
import pyudev

from middlewared.service import CallError, filterable, private, Service
from middlewared.utils import filter_list, run


class DiskService(Service):

    @private
    async def create_swap_mirror(self, name, options):
        extra = options['extra']
        await run('mdadm', '--zero-superblock', '--force', *options['paths'], encoding='utf8', check=False)
        cp = await run(
            'mdadm', '--create', os.path.join('/dev/md', name), f'--level={extra.get("level", 1)}',
            f'--raid-devices={len(options["paths"])}', '--meta=1.2', *options['paths'], encoding='utf8', check=False,
        )
        if cp.returncode:
            raise CallError(f'Failed to create mirror {name}: {cp.stderr}')

    @private
    async def destroy_swap_mirror(self, name):
        mirror = await self.middleware.call('disk.get_swap_mirrors', [['name', '=', name]], {'get': True})
        if mirror['encrypted_provider']:
            await self.middleware.call('disk.remove_encryption', mirror['encrypted_provider'])

        for provider in mirror['providers']:
            await run('mdadm', mirror['real_path'], '--fail', provider['id'], check=False)
            await run('mdadm', mirror['real_path'], '--remove', provider['id'], check=False)

        await self.stop_md_device(mirror['path'])
        await self.clean_superblocks_on_md_device([p['name'] for p in mirror['providers']], True)

    @private
    async def stop_md_device(self, path, raise_exception=True):
        cp = await run('mdadm', '--stop', path, check=False, encoding='utf8')
        if cp.returncode and raise_exception:
            raise CallError(f'Failed to stop md device {path!r}: {cp.stderr}')

    @private
    async def clean_superblocks_on_md_device(self, devices, force):
        await run(*(
            ['mdadm', '--zero-superblock'] + (['--force'] if force else []) + [
                os.path.join('/dev', device) for device in devices
            ]
        ), check=False, encoding='utf8')

    @private
    @filterable
    def get_md_devices(self, filters, options):
        md_devices = []
        context = pyudev.Context()
        with contextlib.suppress(FileNotFoundError):
            for array in os.scandir('/dev/md'):
                real_path = os.path.realpath(array.path)
                md_device = {
                    'name': array.name.split(':')[-1],
                    'path': array.path,
                    'real_path': real_path,
                    'encrypted_provider': None,
                    'providers': [],
                }
                if enc_path := glob.glob(f'/sys/block/dm-*/slaves/{real_path.split("/")[-1]}'):
                    md_device['encrypted_provider'] = os.path.join('/dev', enc_path[0].split('/')[3])

                for provider in os.scandir(os.path.join('/sys/block', md_device['real_path'].split('/')[-1], 'slaves')):
                    provider_data = {'name': provider.name, 'id': provider.name, 'disk': provider.name}

                    partition = os.path.join('/sys/class/block', provider.name, 'partition')
                    if os.path.exists(partition):
                        # This means provider is a partition and not complete disk
                        with contextlib.suppress(pyudev.DeviceNotFoundByNameError):
                            device = pyudev.Devices.from_name(context, 'block', provider.name)
                            parent = device.find_parent('block')
                            if parent is not None:
                                provider_data['disk'] = parent.sys_name

                    md_device['providers'].append(provider_data)

                md_devices.append(md_device)

        return filter_list(md_devices, filters, options)

    @private
    @filterable
    def get_swap_mirrors(self, filters, options):
        filters.append(['name', 'rin', 'swap'])
        return self.get_md_devices(filters, options)

    @private
    async def get_unsupported_md_devices(self):
        return await self.middleware.call('disk.get_md_devices', [['name', 'rnin', 'swap']])

    @private
    async def get_disks_to_unsupported_md_devices_mapping(self):
        md_device_disk_mapping = collections.defaultdict(list)
        for md_device in await self.get_unsupported_md_devices():
            for provider in md_device['providers']:
                md_device_disk_mapping[provider['disk']].append(md_device['name'])
        return md_device_disk_mapping
