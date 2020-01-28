from middlewared.service import private, ServicePartBase


class DiskInfoBase(ServicePartBase):

    @private
    async def get_dev_size(self, dev):
        """
        Return disk/partition size in bytes or None if unable to do so
        """

    @private
    async def list_partitions(self, disk):
        """
        Returns list of partitions of disk if any
        """

    @private
    async def gptid_from_part_type(self, disk, part_type):
        """
        Returns GPT raw UUID for partitioned disk
        """

    @private
    async def get_zfs_part_type(self):
        raise NotImplementedError()

    @private
    async def get_swap_part_type(self):
        raise NotImplementedError()

    @private
    async def get_swap_devices(self):
        raise NotImplementedError()

    async def label_to_dev(self, label, *args):
        raise NotImplementedError()

    @private
    async def label_to_disk(self, label, *args):
        raise NotImplementedError()

    @private
    async def get_disk_from_partition(self, part_name):
        raise NotImplementedError()
