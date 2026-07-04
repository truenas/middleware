from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.utils import run

if TYPE_CHECKING:
    from middlewared.service import ServiceContext


async def serial_port_choices(context: ServiceContext) -> dict[str, str]:
    ports: dict[str, str] = {
        e['name']: e['name'] for e in await context.middleware.call('device.get_info', {'type': 'SERIAL'})
    }
    if not ports or (await context.call2(context.s.system.advanced.config)).serialport == 'ttyS0':
        # We should always add ttyS0 if ports is false or current value is the default one in db
        # i.e ttyS0
        ports['ttyS0'] = 'ttyS0'

    return ports


async def configure_tty(
    context: ServiceContext, old: dict[str, Any], new: dict[str, Any], generate_grub: bool = False
) -> None:
    restart_ttys = any(old[k] != new[k] for k in ('serialconsole', 'serialspeed', 'serialport'))

    if old['serialconsole'] != new['serialconsole']:
        if old['serialport'] == new['serialport']:
            action = 'enable' if new['serialconsole'] else 'disable'
            cp = await run(
                ['systemctl', action, f'serial-getty@{old["serialport"]}.service'], check=False
            )
            if cp.returncode:
                context.logger.error('Failed to %r serialconsole: %r', action, cp.stderr.decode())

    if old['serialport'] != new['serialport']:
        for command in [
            ['systemctl', 'disable', f'serial-getty@{old["serialport"]}.service'],
            ['systemctl', 'stop', f'serial-getty@{old["serialport"]}.service'],
        ] + (
            [['systemctl', 'enable', f'serial-getty@{new["serialport"]}.service']] if new['serialconsole'] else []
        ):
            cp = await run(command, check=False)
            if cp.returncode:
                context.logger.error(
                    'Failed to %r %r serialport service: %r', command[1], command[2], cp.stderr.decode()
                )

    if restart_ttys or old['consolemenu'] != new['consolemenu']:
        serial_action = 'restart' if new['serialconsole'] else 'stop'
        cp = await run(['systemctl', serial_action, f'serial-getty@{new["serialport"]}.service'], check=False)
        if cp.returncode:
            context.logger.error(
                'Failed to %r %r serial port: %r', serial_action, new['serialport'], cp.stderr.decode()
            )

    if old['consolemenu'] != new['consolemenu']:
        cp = await run(['systemctl', 'restart', 'getty@tty1.service'], check=False)
        if cp.returncode:
            context.logger.error('Failed to restart tty service: %r', cp.stderr.decode())

    if generate_grub or restart_ttys:
        await context.middleware.call('etc.generate', 'grub')
        if await context.middleware.call('failover.licensed'):
            try:
                await context.middleware.call('failover.call_remote', 'etc.generate', ['grub'])
            except Exception:
                context.logger.exception('failed to render grub.cfg on remote node')
