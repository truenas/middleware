import os
import signal
import subprocess

from middlewared.utils import osc


def render(service, middleware):
    if osc.IS_LINUX:
        for command in [
            ['systemctl', 'restart', 'getty@tty1.service'],
            ['systemctl', 'restart', 'serial-getty@*.service'],
        ]:
            proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = proc.communicate()
            if proc.returncode:
                middleware.logger.debug('Failed to execute "%s": %s', ' '.join(command), stderr.decode())
    else:
        os.kill(1, signal.SIGHUP)
