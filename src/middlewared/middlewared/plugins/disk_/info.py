from middlewared.service import Service, filterable_api_method, private
from middlewared.utils.filter_list import filter_list


class DiskService(Service):

    @filterable_api_method(private=True)
    async def list_all_partitions(self, filters, options):
        """
        Returns list of all partitions present in the system
        """
        disks = await self.middleware.call('device.get_disks')
        parts = []
        for disk in disks:
            parts.extend(await self.middleware.call('disk.list_partitions', disk))
        return filter_list(parts, filters, options)

    @private
    async def get_partition(self, disk: str):
        # Will retrieve zfs partition on disk if any
        return await self.get_partition_with_uuids(disk, [await self.middleware.call('disk.get_zfs_part_type')])

    @private
    async def get_partition_with_uuids(self, disk, uuids):
        part = next(
            (p for p in await self.middleware.call('disk.list_partitions', disk) if p['partition_type'] in uuids),
            None
        )
        return part
