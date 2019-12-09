from middlewared.service import Service
from middlewared.utils import run

from .wipe_base import WipeDiskBase


class DiskService(Service, WipeDiskBase):

    async def destroy_partitions(self, disk):
        await run('gpart', 'destroy', '-F', f'/dev/{disk}', check=False)

        # Wipe out the partition table by doing an additional iterate of create/destroy
        await run('gpart', 'create', '-s', 'gpt', f'/dev/{disk}')
        await run('gpart', 'destroy', '-F', f'/dev/{disk}')
