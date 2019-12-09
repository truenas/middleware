import blkid

from middlewared.service import Service
from middlewared.utils import run

from .wipe_base import WipeDiskBase


class DiskService(Service, WipeDiskBase):

    async def wipe_quick(self, dev, size=None):
        # If the size is too small, lets just skip it for now.
        # In the future we can adjust dd size
        if size and size < 33554432:
            return
        await run('dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1m', 'count=32')
        try:
            size = blkid.BlockDevice(dev).size
        except blkid.BlkidException:
            self.logger.error(f'Unable to determine size of {dev}')
        else:
            # This will fail when EOL is reached
            await run('dd', 'if=/dev/zero', f'of=/dev/{dev}', 'bs=1m', f'oseek={int(size / 1024) - 32}', check=False)

    def wipe(self, job, dev, mode, sync):
        raise NotImplementedError()
