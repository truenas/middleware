from middlewared.schema import accepts, Dict, returns
from middlewared.service import Service


class SystemAdvancedService(Service):

    class Config:
        namespace = 'system.advanced'
        cli_namespace = 'system.advanced'

    @accepts()
    @returns(Dict('serial_port_choices', additional_attrs=True))
    async def serial_port_choices(self):
        """
        Get available choices for `serialport`.
        """
        ports = {e['name']: e['name'] for e in await self.middleware.call('device.get_info', 'SERIAL')}
        if not ports or (await self.middleware.call('system.advanced.config'))['serialport'] == 'ttyS0':
            # We should always add ttyS0 if ports is false or current value is the default one in db
            # i.e ttyS0
            ports['ttyS0'] = 'ttyS0'

        return ports


