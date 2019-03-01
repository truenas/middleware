import subprocess


def fstab_configuration(middleware):
    ret = subprocess.run(
        ['mount', '-uw', '/'],
        capture_output=True
    )
    if ret.returncode:
        middleware.logger.debug(f'Failed to execute "mount -uw": {ret.stderr.decode()}')


def render(service, middleware):
    fstab_configuration(middleware)
