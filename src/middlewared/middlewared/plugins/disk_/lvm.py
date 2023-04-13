import os

from middlewared.service import private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def remove_lvm_from_disks(self, disks):
        """
        Remove LVM from disks.
        """
        lvm_to_disk_mapping = await self.middleware.call('device.list_lvm_to_disk_mapping')
        to_remove_lvm_paths = []
        for disk in disks:
            if disk not in lvm_to_disk_mapping:
                continue

            for entry in lvm_to_disk_mapping[disk]:
                to_remove_lvm_paths.extend(['-f', os.path.join('/dev', *entry)])

        if to_remove_lvm_paths:
            await run(
                ['lvremove'] + to_remove_lvm_paths, check=False, encoding='utf8', errors='ignore',
            )
