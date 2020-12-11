import contextlib
import os
import shutil
import subprocess

from middlewared.utils import osc


def localtime_configuration(middleware):
    system_config = middleware.call_sync('system.general.config')
    if not system_config['timezone']:
        system_config['timezone'] = 'America/Los_Angeles'

    if osc.IS_LINUX:
        with contextlib.suppress(OSError):
            os.unlink('/etc/localtime')
        os.symlink(os.path.join('/usr/share/zoneinfo', system_config['timezone']), '/etc/localtime')
        cp = subprocess.Popen(
            ['systemctl', 'daemon-reload'], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE
        )
        stderr = cp.communicate()[1]
        if cp.returncode:
            middleware.logger.error(
                'Failed to reload systemctl daemon after timezone configuration: %s', stderr.decode()
            )
    else:
        shutil.copy(
            os.path.join('/usr/share/zoneinfo/', system_config['timezone']),
            '/etc/localtime'
        )

        with open('/var/db/zoneinfo', 'w') as f:
            f.write(f'{system_config["timezone"]}\n')


def render(service, middleware):
    localtime_configuration(middleware)
