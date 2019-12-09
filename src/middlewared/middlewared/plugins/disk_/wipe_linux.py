from middlewared.service import Service
from middlewared.utils import run

from .wipe_base import WipeDiskBase


class DiskService(Service, WipeDiskBase):

    async def destroy_partitions(self, disk):
        cp = await run(['sgdisk', '-Z', disk])
        return cp.returncode == 0
