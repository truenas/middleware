from middlewared.schema import accepts, Dict, returns
from middlewared.service import private, Service
from middlewared.utils import run


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

    @private
    async def configure_tty(self, old, new, generate_grub=False):
        restart_ttys = any(old[k] != new[k] for k in ('serialconsole', 'serialspeed', 'serialport'))

        if old['serialconsole'] != new['serialconsole']:
            if old['serialport'] == new['serialport']:
                action = 'enable' if new['serialconsole'] else 'disable'
                cp = await run(
                    ['systemctl', action, f'serial-getty@{old["serialport"]}.service'], check=False
                )
                if cp.returncode:
                    self.logger.error('Failed to %r serialconsole: %r', action, cp.stderr.decode())

        if old['serialport'] != new['serialport']:
            for command in [
               ['systemctl', 'disable', f'serial-getty@{old["serialport"]}.service'],
               ['systemctl', 'stop', f'serial-getty@{old["serialport"]}.service'],
            ] + (
                [['systemctl', 'enable', f'serial-getty@{new["serialport"]}.service']] if new['serialconsole'] else []
            ):
                cp = await run(command, check=False)
                if cp.returncode:
                    self.logger.error(
                        'Failed to %r %r serialport service: %r', command[1], command[2], cp.stderr.decode()
                    )

        if restart_ttys or new['consolemenu'] != new['consolemenu']:
            await self.middleware.call('service.start', 'ttys')

        if new['consolemenu'] != new['consolemenu']:
            await self.middleware.call('service.start', 'tty')

        if generate_grub or restart_ttys:
            await self.middleware.call('etc.generate', 'grub')
