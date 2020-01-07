import os

from middlewared.service import private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def dumpdev_configure(self, name):
        # Configure dumpdev on first swap device
        if not os.path.exists('/dev/dumpdev'):
            try:
                os.unlink('/dev/dumpdev')
            except OSError:
                pass
            os.symlink(f'/dev/{name}', '/dev/dumpdev')
            await run('dumpon', f'/dev/{name}')
        return True
