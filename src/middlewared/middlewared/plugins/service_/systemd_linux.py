from middlewared.service import private, Service


class ServiceService(Service):

    @private
    async def systemd_units(self, name):
        service = await self.middleware.call('service.object', name)
        if service.systemd_unit == NotImplemented:
            return []
        else:
            return [service.systemd_unit] + await service.systemd_extra_units()

    @private
    async def systemd_enabled_units(self, name, config_db=None):
        service = await self.middleware.call('service.object', name)
        return await service.systemd_enabled_units(config_db)
