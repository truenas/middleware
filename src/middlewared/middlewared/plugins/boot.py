from middlewared.schema import Bool, Dict, Str, accepts
from middlewared.service import Service


class BootService(Service):

    @accepts()
    def get_disks(self):
        """
        Returns disks of the boot pool.
        """
        return self.middleware.call('zfs.pool.get_disks', 'freenas-boot')
