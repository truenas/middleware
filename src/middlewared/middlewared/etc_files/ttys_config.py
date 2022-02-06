from middlewared.utils import run


async def render(service, middleware):
    serial_action = 'restart' if (await middleware.call('system.advanced.config'))['serialconsole'] else 'stop'
    for command in [
        ['systemctl', 'restart', 'getty@tty1.service'],
        ['systemctl', serial_action, 'serial-getty@*.service'],
    ]:
        cp = await run(command, check=False)
        if cp.returncode:
            middleware.logger.debug('Failed to execute "%s": %s', ' '.join(command), cp.stderr.decode())
