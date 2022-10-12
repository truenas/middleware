from middlewared.service import private, Service
from middlewared.utils.asyncio_ import asyncio_map


class PoolService(Service):

    @private
    async def format_disks(self, job, disks):
        """
        Format all disks, putting all freebsd-zfs partitions created
        into their respective vdevs and encrypting disks if specified for FreeBSD.
        """
        # Make sure all SED disks are unlocked
        await self.middleware.call('disk.sed_unlock_all')
        swapgb = (await self.middleware.call('system.advanced.config'))['swapondrive']
        formatted = 0
        await self.middleware.call('pool.remove_unsupported_md_devices_from_disks', disks)

        async def format_disk(arg):
            nonlocal formatted
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

        await asyncio_map(format_disk, disks.items(), limit=16)

        disk_sync_job = await self.middleware.call('disk.sync_all')
        await job.wrap(disk_sync_job)
