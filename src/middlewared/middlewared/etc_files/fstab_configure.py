import subprocess


def fstab_configuration(middleware):
    for command in [
        ['systemctl', 'daemon-reload'],
        ['systemctl', 'restart', 'local-fs.target'],
    ]:
        ret = subprocess.run(command, capture_output=True)
        if ret.returncode:
            middleware.logger.debug(f'Failed to execute "{" ".join(command)}": {ret.stderr.decode()}')


def render(service, middleware):
    fstab_configuration(middleware)
