from middlewared.service import private, Service


class ServiceService(Service):

    @private
    async def systemd_units(self, name):
        service = await self.middleware.call('service.object', name)
        return [service.systemd_unit] + service.systemd_extra_units
