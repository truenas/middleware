import blkid

from middlewared.service import Service, ServiceChangeMixin

from .sync_base import DiskSyncBase


class DiskService(Service, DiskSyncBase, ServiceChangeMixin):

    async def device_to_identifier(self, name):
        disks = await self.middleware.call('device.get_disk')
        if name not in disks:
            return ''
        else:
            block_device = disks[name]

        if block_device['serial']:
            return f'{{serial}}{block_device["serial"]}'

        if block_device['uuid']:
            return f'{{uuid}}{block_device["uuid"]}'
        if block_device['label']:
            return f'{{label}}{block_device["label"]}'
        return f'{{devicename}}{name}'

    async def identifier_to_device(self, ident):
        raise NotImplementedError()

    async def sync_all(self, job):
        raise NotImplementedError()

    async def sync(self, name):
        raise NotImplementedError()
