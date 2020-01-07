from middlewared.service import private, Service


class DiskService(Service):
    @private
    async def toggle_smart_off(self, devname):
        await self.middleware.call('disk.smartctl', devname, ['--smart=off'], {'silent': True})

    @private
    async def toggle_smart_on(self, devname):
        await self.middleware.call('disk.smartctl', devname, ['--smart=on'], {'silent': True})
