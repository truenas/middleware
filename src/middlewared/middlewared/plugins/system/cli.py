import contextlib
import os
import signal

from middlewared.service import Service, private
from middlewared.utils.os import get_pids


class SystemService(Service):
    @private
    def reload_cli(self):
        for process in filter(lambda x: x and b'/usr/bin/cli' in x.cmdline, get_pids()):
            args = process.cmdline.split(b' ')
            if len(args) >= 2 and args[1] == b'/usr/bin/cli':
                with contextlib.suppress(Exception):
                    os.kill(process.pid, signal.SIGUSR1)
