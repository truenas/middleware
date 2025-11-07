from middlewared.service import private, Service
from middlewared.service_exception import CallError
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks, base_percentage=0, upper_percentage=100):
        """
        Format all disks, putting all ZFS partitions created into their respective vdevs.
        """
        formatted = 0
        len_disks = len(disks)
        current_percentage = base_percentage
        single_disk_percentage = (upper_percentage - base_percentage) / len_disks

        async def unlock_and_format_disk(arg):
            nonlocal formatted, current_percentage
            disk, config = arg
            if await self.middleware.call('disk.sed_unlock_impl', disk, True) is False:
                # returns None or boolean, None we can safely ignore
                raise CallError(f"Failed to unlock {disk!r}. Check /var/log/middlewared.log")
            await self.middleware.call('disk.format', disk, config.get('size'))
            formatted += 1
            current_percentage += single_disk_percentage
            job.set_progress(current_percentage, f'Formatting disks ({formatted}/{len_disks})')

        await asyncio_map(unlock_and_format_disk, disks.items(), limit=16)

        disk_sync_job = await self.middleware.call('disk.sync_all')
        await disk_sync_job.wait(raise_error=True)

        zfs_part_type = await self.middleware.call('disk.get_zfs_part_type')
        for disk, config in disks.items():
            devname = await self.middleware.call('disk.gptid_from_part_type', disk, zfs_part_type)
            config['vdev'].append(f'/dev/{devname}')
