from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks):
        """
        Format all disks, putting all ZFS partitions created  into their respective vdevs.
        """
        # Make sure all SED disks are unlocked
        await self.middleware.call('disk.sed_unlock_all')
        swapgb = (await self.middleware.call('system.advanced.config'))['swapondrive']
        formatted = 0
        await self.middleware.call('pool.remove_unsupported_md_devices_from_disks', disks)
        is_ha_capable = await self.middleware.call('system.is_ha_capable')
        len_disks = len(disks)

        async def format_disk(arg):
            nonlocal formatted
            disk, config = arg
            swap_size = 0
            if config['create_swap'] and not is_ha_capable:
                swap_size = swapgb
            await self.middleware.call('disk.format', disk, config.get('min_size'), swap_size, False)
            formatted += 1
            job.set_progress(15, f'Formatting disks ({formatted}/{len_disks})')

        await asyncio_map(format_disk, disks.items(), limit=16)

        disk_sync_job = await self.middleware.call('disk.sync_all')
        await job.wrap(disk_sync_job)

        zfs_part_type = await self.middleware.call('disk.get_zfs_part_type')
        for disk, config in disks.items():
            devname = await self.middleware.call('disk.gptid_from_part_type', disk, zfs_part_type)
            config['vdev'].append(f'/dev/{devname}')
