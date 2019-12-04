from middlewared.service import Service, ServiceChangeMixin

from .sync_base import DiskSyncBase


class DiskService(Service, DiskSyncBase, ServiceChangeMixin):

    async def serial_from_device(self, name):
        raise NotImplementedError()

    async def device_to_identifier(self, name):
        raise NotImplementedError()

    async def identifier_to_device(self, ident):
        raise NotImplementedError()

    async def sync_all(self, job):
        raise NotImplementedError()

    async def sync(self, name):
        raise NotImplementedError()
