from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks):
        """
        Format all disks, putting all ZFS partitions created into their respective vdevs.
        """
        # Make sure all SED disks are unlocked
        await self.middleware.call('disk.sed_unlock_all')

        swapgb = (await self.middleware.call('system.advanced.config'))['swapondrive']

        enc_disks = []
        formatted = 0

        async def format_disk(arg):
            nonlocal enc_disks, formatted
            disk, config = arg
            await self.middleware.call(
                'disk.format', disk, swapgb if config['create_swap'] else 0, False,
            )
            devname = await self.middleware.call(
                'disk.gptid_from_part_type', disk, await self.middleware.call('disk.get_zfs_part_type')
            )
            formatted += 1
            job.set_progress(15, f'Formatting disks ({formatted}/{len(disks)})')
            config['vdev'].append(f'/dev/{devname}')

        job.set_progress(15, f'Formatting disks (0/{len(disks)})')

        await asyncio_map(format_disk, disks.items(), limit=16)

        await self.middleware.call('disk.sync_all')

        return enc_disks
