import logging
import os
import signal
import time

import psutil

from .base import SimpleService, ServiceState

logger = logging.getLogger(__name__)


class SMARTDService(SimpleService):
    name = "smartd"
    reloadable = True

    etc = ["rc", "smartd"]

    freebsd_rc = "smartd-daemon"
    freebsd_pidfile = "/var/run/smartd-daemon.pid"
    freebsd_procname = "smartd"

    systemd_unit = "smartmontools"
    systemd_async_start = True

    async def _get_state_freebsd(self):
        result = await super()._get_state_freebsd()
        if result.running:
            return result

        if await self.middleware.run_in_thread(self._freebsd_initializing_smartd_pid) is not None:
            return ServiceState(True, [])

        return ServiceState(False, [])

    def _freebsd_initializing_smartd_pid(self):
        """
        smartd initialization can take a long time if lots of disks are present
        It only writes pidfile at the end of the initialization but forks immediately
        This method returns PID of smartd process that is still initializing and has not written pidfile yet
        """
        if os.path.exists(self.freebsd_pidfile):
            # Already started, no need for special handling
            return

        for process in psutil.process_iter(attrs=["cmdline", "create_time"]):
            if process.info["cmdline"][:1] == ["/usr/local/sbin/smartd"]:
                break
        else:
            # No smartd process present
            return

        lifetime = time.time() - process.info["create_time"]
        if lifetime < 300:
            # Looks like just the process we need
            return process.pid

        logger.warning("Got an orphan smartd process: pid=%r, lifetime=%r", process.pid, lifetime)

    async def _stop_freebsd(self):
        pid = await self.middleware.run_in_thread(self._freebsd_initializing_smartd_pid)
        if pid is None:
            return await super()._stop_freebsd()

        os.kill(pid, signal.SIGKILL)

    async def _reload_freebsd(self):
        pid = await self.middleware.run_in_thread(self._freebsd_initializing_smartd_pid)
        if pid is None:
            return await super()._reload_freebsd()

        os.kill(pid, signal.SIGKILL)

        await self._start_freebsd()
