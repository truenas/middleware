from middlewared.service import filterable_api_method, private, Service
from middlewared.utils import filter_list
from middlewared.utils.disks_.disk_class import DiskEntry
from middlewared.utils.disks_.gpt_parts import PART_TYPES


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
    def get_partition(self, disk: str):
        # Will retrieve zfs partition on disk if any
        disk_obj = DiskEntry(name=disk, devpath=f'/dev/{disk}')
        part = next(
            (p.to_dict() for p in (disk_obj.partitions() if disk_obj.is_valid() else []) if PART_TYPES.get(
                p.partition_type
            ) == 'ZFS'),
            None
        )
        return part
