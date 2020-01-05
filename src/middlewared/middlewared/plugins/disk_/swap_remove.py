import os
import platform

from middlewared.service import private, Service
from middlewared.utils import run

IS_LINUX = platform.system().lower() == 'linux'


class DiskService(Service):

    @private
    async def swaps_remove_disks(self, disks):
        """
        Remove a given disk (e.g. ["da0", "da1"]) from swap.
        it will offline if from swap, remove it from the gmirror (if exists)
        and detach the geli.
        """
        providers = {}
        for disk in disks:
            partitions = await self.middleware.call('disk.list_partitions', disk)
            if not partitions:
                continue
            for p in partitions:
                if p['partition_type'] in await self.middleware.call('disk.get_valid_swap_partition_type_uuids'):
                    providers[p['id']] = p
                    break

        if not providers:
            return

        mirrors = set()
        mirror_data = {m['path']: m for m in await self.middleware.call('disk.get_swap_mirrors')}
        for mirror in mirror_data.values():
            for provider in mirror['providers']:
                if providers.pop(provider['id'], None):
                    mirrors.add(mirror['path'] if IS_LINUX else mirror['name'])

        swap_devices = await self.middleware.call('disk.get_swap_devices')

        for name in mirrors:
            devname = name if IS_LINUX else f'mirror/{name}.eli'
            if devname in swap_devices:
                await run('swapoff', name if IS_LINUX else os.path.join('/dev', devname))
            if IS_LINUX:
                await run('mdadm', '--stop', name)
                await run(
                    'mdadm', '--zero-superblock', *(
                        os.path.join('/dev', p['name']) for p in mirror_data[name]['providers']
                    )
                )
            else:
                if os.path.exists(os.path.join('/dev', devname)):
                    await run('geli', 'detach', devname)
                await run('gmirror', 'destroy', name)

        for p in providers.values():
            devname = os.path.join('/dev', p['name']) if IS_LINUX else f'{p["name"]}.eli'
            if devname in swap_devices:
                await run('swapoff', devname if IS_LINUX else os.path.join('/dev', devname))
            if not IS_LINUX and os.path.exists(f'/dev/{devname}'):
                await run('geli', 'detach', devname)
