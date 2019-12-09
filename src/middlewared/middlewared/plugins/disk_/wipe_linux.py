import os

from middlewared.service import Service
from middlewared.utils import run

from .wipe_base import WipeDiskBase


class DiskService(Service, WipeDiskBase):

    async def destroy_partitions(self, disk):
        await run(['sgdisk', '-Z', os.path.join('/dev', disk)])
