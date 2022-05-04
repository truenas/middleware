from middlewared.plugins.service_.services.base import SimpleService, ServiceState


class RoutingService(SimpleService):
    name = 'routing'
    freebsd_rc = 'routing'
    restartable = True

    async def _get_state_freebsd(self):
        return ServiceState(True, [])
