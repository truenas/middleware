import os

from middlewared.utils.osc import IS_LINUX
from middlewared.service import job, private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    @job(lock='swaps_configure')
    async def swaps_remove_disks(self, disks):
        """
        Remove a given disk (e.g. ["da0", "da1"]) from swap.
        It will offline if from swap, removing encryption and destroying the mirror ( if part of one ).
        """
        return await self.swaps_remove_disks_internal(disks)

    @private
    async def swaps_remove_disks_internal(self, disks):
        """
        We have a separate endpoint for this to ensure that no other swap related operations not do swap devices
        removal while swap configuration is in progress - however we still need to allow swap configuration process
        to remove swap devices and it can use this endpoint directly for that purpose.
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

        swap_devices = await self.middleware.call('disk.get_swap_devices')
        for mirror in await self.middleware.call('disk.get_swap_mirrors'):
            destroyed_mirror = False
            for provider in mirror['providers']:
                if providers.pop(provider['id'], None) and not destroyed_mirror:
                    devname = mirror['encrypted_provider'] or mirror['real_path']
                    if devname in swap_devices:
                        await run('swapoff', devname)
                    if mirror['encrypted_provider']:
                        await self.middleware.call(
                            'disk.remove_encryption', mirror['encrypted_provider']
                        )
                    await self.middleware.call('disk.destroy_swap_mirror', mirror['name'])
                    destroyed_mirror = True

        configure_swap = False
        for p in providers.values():
            devname = p['encrypted_provider'] or p['path']
            if devname in swap_devices:
                await run('swapoff', devname)
            if p['encrypted_provider']:
                await self.middleware.call('disk.remove_encryption', p['encrypted_provider'])
            if not IS_LINUX and os.path.realpath('/dev/dumpdev') == p['path']:
                configure_swap = True
                try:
                    os.unlink('/dev/dumpdev')
                except OSError:
                    pass

        if configure_swap:
            await self.middleware.call('disk.swaps_configure')
