import subprocess


def fstab_configuration(middleware):
    ret = subprocess.run(
        ['mount', '-uw'],
        capture_output=True
    )
    if ret.returncode:
        middleware.logger.debug(f'Failed to execute "mount -uw": {ret.stderr}')


async def render(service, middleware):
    await middleware.run_in_thread(fstab_configuration, middleware)
