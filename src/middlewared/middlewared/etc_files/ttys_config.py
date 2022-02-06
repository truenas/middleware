from middlewared.utils import run


async def render(service, middleware):
    for command in [
        ['systemctl', 'restart', 'getty@tty1.service'],
        ['systemctl', 'restart', 'serial-getty@*.service'],
    ]:
        cp = await run(command, check=False)
        if cp.returncode:
            middleware.logger.debug('Failed to execute "%s": %s', ' '.join(command), cp.stderr.decode())
