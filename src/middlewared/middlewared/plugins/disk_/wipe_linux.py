from middlewared.service import Service

from .wipe_base import WipeDiskBase


class DiskService(Service, WipeDiskBase):

    async def destroy_partitions(self, disk):
        raise NotImplementedError()
