from middlewared.plugins.service_.services.base import SimpleService, ServiceState


class HostnameService(SimpleService):
    name = 'hostname'
    freebsd_rc = 'hostname'
    restartable = True

    async def _get_state_freebsd(self):
        return ServiceState(True, [])
