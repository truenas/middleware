import logging
import os
import subprocess
import threading
import time

from middlewared.utils import run

from .base_state import ServiceState

logger = logging.getLogger(__name__)


class SimpleServiceFreeBSD:
    freebsd_rc = NotImplemented
    freebsd_pidfile = None
    freebsd_procname = None

    async def _get_state_freebsd(self):
        procname = self.freebsd_procname or self.freebsd_rc

        if self.freebsd_pidfile:
            cmd = ["pgrep", "-F", self.freebsd_pidfile, procname]
        else:
            cmd = ["pgrep", procname]

        proc = await run(*cmd, check=False, encoding="utf-8")
        if proc.returncode == 0:
            return ServiceState(True, [
                int(i)
                for i in proc.stdout.strip().split('\n') if i.isdigit()
            ])
        else:
            return ServiceState(False, [])

    async def _start_freebsd(self):
        sn = None
        if self.freebsd_pidfile is not None:
            sn = FreeBSDStartNotify(self.freebsd_pidfile, "start")
            sn.start()

        await self._freebsd_service(self.freebsd_rc, "restart")

        if sn is not None:
            await self.middleware.run_in_thread(sn.join)

    async def _stop_freebsd(self):
        sn = None
        if self.freebsd_pidfile is not None:
            sn = FreeBSDStartNotify(self.freebsd_pidfile, "stop")
            sn.start()

        await self._freebsd_service(self.freebsd_rc, "stop", force=True)

        if sn is not None:
            await self.middleware.run_in_thread(sn.join)

    async def _restart_freebsd(self):
        sn = None
        if self.freebsd_pidfile is not None:
            sn = FreeBSDStartNotify(self.freebsd_pidfile, "restart")
            sn.start()

        await self._freebsd_service(self.freebsd_rc, "restart")

        if sn is not None:
            await self.middleware.run_in_thread(sn.join)

    async def _reload_freebsd(self):
        await self._freebsd_service(self.freebsd_rc, "reload")

    async def _freebsd_service(self, rc, verb, force=False):
        if force:
            preverb = "force"
        else:
            preverb = "one"

        return await freebsd_service(rc, preverb + verb)

    async def _identify_freebsd(self, procname):
        return procname == (self.freebsd_procname or self.freebsd_rc)


class FreeBSDStartNotify(threading.Thread):
    def __init__(self, pidfile, verb, *args, **kwargs):
        self._pidfile = pidfile
        self._verb = verb

        try:
            with open(self._pidfile) as f:
                self._pid = f.read()
        except IOError:
            self._pid = None

        super().__init__(*args, **kwargs, daemon=True)

    def run(self):
        """
        If we are using start or restart we expect that a .pid file will
        exists at the end of the process, so we wait for said pid file to
        be created and check if its contents are non-zero.
        Otherwise we will be stopping and expect the .pid to be deleted,
        so wait for it to be removed
        """
        tries = 1
        while tries < 6:
            time.sleep(1)
            if self._verb in ("start", "restart"):
                if os.path.exists(self._pidfile):
                    # The file might have been created but it may take a
                    # little bit for the daemon to write the PID
                    time.sleep(0.1)
                try:
                    with open(self._pidfile) as f:
                        pid = f.read()
                except IOError:
                    pid = None

                if pid:
                    if self._verb == "start":
                        break
                    if self._verb == "restart":
                        if pid != self._pid:
                            break
                        # Otherwise, service has not restarted yet
            elif self._verb == "stop" and not os.path.exists(self._pidfile):
                break
            tries += 1


async def freebsd_service(rc, verb):
    result = await run("service", rc, verb, check=False, encoding="utf-8", stderr=subprocess.STDOUT)
    if not verb.endswith("status") and result.returncode != 0:
        logger.warning("%s %s failed with code %d: %r", rc, verb, result.returncode, result.stdout)

    return result
