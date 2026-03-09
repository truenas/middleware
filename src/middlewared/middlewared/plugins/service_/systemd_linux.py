from middlewared.service import private, Service


class ServiceService(Service):

    @private
    async def systemd_units(self, name):
        service = await self.middleware.call('service.object', name)
        if hasattr(service, 'systemd_unit'):
            return [service.systemd_unit] + await service.systemd_extra_units()
        return []
