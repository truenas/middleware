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
            cp = await run('dumpon', f'/dev/{name}', check=False)
            if cp.returncode:
                self.middleware.logger.error(
                    'Failed to specify "%s" device for crash dumps: %s', f'/dev/{name}', cp.stderr.decode()
                )
            else:
                self.middleware.logger.debug('Configured "%s" device for crash dumps.', f'/dev/{name}')
        return True
