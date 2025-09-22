from middlewared.service import private, Service
from middlewared.utils.disks_.disk_class import DiskEntry
from middlewared.utils.disks_.gpt_parts import PART_TYPES


class DiskService(Service):

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
