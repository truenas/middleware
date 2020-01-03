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
        for mirror in await self.middleware.call('disk.get_swap_mirrors'):
            for provider in mirror['providers']:
                if providers.pop(provider):
                    mirrors.add(mirror['name'])

        swap_devices = await self.middleware.call('disk.get_swap_devices')

        for name in mirrors:
            if not IS_LINUX:
                devname = f'mirror/{name}.eli'
                devpath = f'/dev/{devname}'
                if devname in swap_devices:
                    await run('swapoff', devpath)
                if os.path.exists(devpath):
                    await run('geli', 'detach', devname)
                await run('gmirror', 'destroy', name)

        for p in providers.values():
            if not IS_LINUX:
                devname = f'{p["name"]}.eli'
                if devname in swap_devices:
                    await run('swapoff', f'/dev/{devname}')
                if os.path.exists(f'/dev/{devname}'):
                    await run('geli', 'detach', devname)
