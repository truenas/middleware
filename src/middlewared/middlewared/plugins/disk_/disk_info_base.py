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
