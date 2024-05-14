from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks):
        """
        Format all disks, putting all ZFS partitions created into their respective vdevs.
        """
        await self.middleware.call('disk.sed_unlock_all')
        await self.middleware.call('pool.remove_unsupported_md_devices_from_disks', disks)

        formatted = 0
        len_disks = len(disks)
        async def format_disk(arg):
            nonlocal formatted
            disk, config = arg
            await self.middleware.call('disk.format', disk)
            formatted += 1
            job.set_progress(15, f'Formatting disks ({formatted}/{len_disks})')

        await asyncio_map(format_disk, disks.items(), limit=16)

        disk_sync_job = await self.middleware.call('disk.sync_all')
        await job.wrap(disk_sync_job)

        zfs_part_type = await self.middleware.call('disk.get_zfs_part_type')
        for disk, config in disks.items():
            devname = await self.middleware.call('disk.gptid_from_part_type', disk, zfs_part_type)
            config['vdev'].append(f'/dev/{devname}')
