import os
import shutil
import subprocess

from middlewared.utils import osc


def localtime_configuration(middleware):
    system_config = middleware.call_sync('system.general.config')
    if not system_config['timezone']:
        system_config['timezone'] = 'America/Los_Angeles'

    if osc.IS_LINUX:
        cp = subprocess.Popen(
            ['timedatectl', 'set-timezone', system_config['timezone']],
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        _, stderr = cp.communicate()
        if cp.returncode:
            middleware.logger.error('Failed to setup timezone to %r: %s', system_config['timezone'], stderr.decode())
    else:
        shutil.copy(
            os.path.join('/usr/share/zoneinfo/', system_config['timezone']),
            '/etc/localtime'
        )

        with open('/var/db/zoneinfo', 'w') as f:
            f.write(f'{system_config["timezone"]}\n')


def render(service, middleware):
    localtime_configuration(middleware)
