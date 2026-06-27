from middlewared.service import Service, private


class ServiceService(Service):

    @private
    async def systemd_units(self, name: str) -> list[str]:
        service = await self.middleware.call('service.object', name)
        if hasattr(service, 'systemd_unit'):
            return [service.systemd_unit] + await service.systemd_extra_units()  # type: ignore[no-any-return]
        return []
