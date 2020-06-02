from middlewared.service import private, Service


class DiskService(Service):
    @private
    async def toggle_smart_off(self, name):
        await self.middleware.call('disk.smartctl', name, ['--smart=off'], {'silent': True})

    @private
    async def toggle_smart_on(self, name):
        await self.middleware.call('disk.smartctl', name, ['--smart=on'], {'silent': True})
