from middlewared.service import CallError, private, Service
from middlewared.utils import run


class DiskService(Service):

    @private
    async def label(self, dev, label):
        cp = await run('geom', 'label', 'label', label, dev, check=False)
        if cp.returncode != 0:
            raise CallError(f'Failed to label {dev}: {cp.stderr.decode()}')
