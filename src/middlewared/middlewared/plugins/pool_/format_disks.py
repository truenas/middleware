from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks):
        """
        This does a few things:
            1. wipes the disks (max of 16 in parallel)
            2. formats the disks with a freebsd-zfs partition label
            3. formats the disks with a freebsd-swap partition lable (if necessary)
            4. regenerates the geom xml cache (geom.cache.invalidate)
        """
        await self.middleware.call('disk.sed_unlock_all')  # unlock any SED drives
        swapgb = (await self.middleware.call('system.advanced.config'))['swapondrive']
        total_disks = len(disks)
        formatted = 0

        async def format_disk(args):
            nonlocal formatted
            disk, config = args
            await self.middleware.call('disk.format', disk, swapgb if config['create_swap'] else 0, False)
            formatted += 1
            job.set_progress(15, f'Formatted disk ({formatted}/{total_disks})')

        await asyncio_map(format_disk, disks.items(), limit=16)
        await self.middleware.call('geom.cache.invalidate')
