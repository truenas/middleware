from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import Service


class BootService(Service):

    @accepts()
    async def get_disks(self):
        """
        Returns disks of the boot pool.
        """
        return await self.middleware.call('zfs.pool.get_disks', 'freenas-boot')
