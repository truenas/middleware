import contextlib
import signal

import psutil

from middlewared.service import Service, private


class SystemService(Service):
    @private
    def reload_cli(self):
        for process in psutil.process_iter(['pid', 'cmdline']):
            cmdline = process.cmdline()
            if len(cmdline) >= 2 and cmdline[1] == '/usr/bin/cli':
                with contextlib.suppress(Exception):
                    process.send_signal(signal.SIGUSR1)
