from middlewared.service import Service, ServiceChangeMixin
from middlewared.utils import run

from .sync_base import DiskSyncBase


class DiskService(Service, DiskSyncBase, ServiceChangeMixin):

    async def serial_from_device(self, name):
        output = await self.middleware.call('disk.smartctl', name, ['-i'], {'silent': True})
        if output:
            search = self.RE_SERIAL_NUMBER.search(output)
            if search:
                return search.group('serial')

        # TODO: Add more and pperhaps improve this one as well
        cp = await run(['lsblk', '--nodeps', '-no', 'serial', f'/dev/{name}'], check=False, encoding='utf8')
        if not cp.returncode and cp.stdout.strip():
            return cp.stdout.strip()
        return None

    async def device_to_identifier(self, name):
        raise NotImplementedError()

    async def identifier_to_device(self, ident):
        raise NotImplementedError()

    async def sync_all(self, job):
        raise NotImplementedError()

    async def sync(self, name):
        raise NotImplementedError()
