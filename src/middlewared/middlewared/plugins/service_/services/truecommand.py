from .base import SimpleService, ServiceState


class TruecommandService(SimpleService):
    name = 'truecommand'

    etc = ['rc', 'truecommand']

    freebsd_rc = 'wireguard'
    freebsd_procname = 'wg-quick'
    freebsd_proc_arguments_match = True

    systemd_unit = 'wg-quick@wg0'

    async def _start_freebsd(self):
        await self._freebsd_service(self.freebsd_rc, 'start')

    async def _get_state_freebsd(self):
        status = (await self._freebsd_service(self.freebsd_rc, 'status')).stdout
        return ServiceState("Device not configured" not in status, [])
