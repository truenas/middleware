from middlewared.service import private, ServicePartBase


class WipeDiskBase(ServicePartBase):

    @private
    async def destroy_partitions(self, disk):
        """
        Destroy partitions of disk if any
        """
