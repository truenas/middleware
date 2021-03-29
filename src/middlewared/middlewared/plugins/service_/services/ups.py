import asyncio
import contextlib
import os
import signal

import psutil

from middlewared.utils import run

from .base import SimpleService


class UPSService(SimpleService):
    name = "ups"

    etc = ["ups"]

    freebsd_rc = "upsd"
    # We use upsmon state
    freebsd_pidfile = "/var/db/nut/upsmon.pid"
    freebsd_procname = "upsmon"

    systemd_unit = "nut-monitor"

    async def systemd_extra_units(self):
        return ["nut-server"] if (await self.middleware.call("ups.config"))["mode"] == "MASTER" else []

    async def before_start(self):
        await self.middleware.call("ups.dismiss_alerts")

    async def _start_freebsd(self):
        if (await self.middleware.call("ups.config"))["mode"] == "MASTER":
            await self._freebsd_service("nut", "start")
        await self._freebsd_service("nut_upsmon", "start")
        await self._freebsd_service("nut_upslog", "start")

    async def _start_linux(self):
        if (await self.middleware.call("ups.config"))["mode"] == "MASTER":
            await self._systemd_unit("nut-server", "start")
        await self._unit_action("Start")

    async def after_start(self):
        if await self.middleware.call("service.started", "collectd"):
            asyncio.ensure_future(self.middleware.call("service.restart", "collectd"))

    async def before_stop(self):
        await self.middleware.call("ups.dismiss_alerts")

    async def _stop_linux(self):
        await self._unit_action("Stop")
        await self._systemd_unit("nut-server", "stop")

    async def _stop_freebsd(self):
        await self._freebsd_service("nut_upslog", "stop", force=True)
        await self._freebsd_service("nut_upsmon", "stop", force=True)
        await self._freebsd_service("nut", "stop", force=True)

        # We need to wait on upsmon service to die properly as multiple processes are
        # associated with it and in most cases they haven't exited when a restart is initiated
        # for upsmon which fails as the older process is still running.
        upsmon_processes = await run(["pgrep", "-x", "upsmon"], encoding="utf-8", check=False)
        if upsmon_processes.returncode == 0:
            gone, alive = await self.middleware.run_in_thread(
                psutil.wait_procs,
                map(
                    lambda v: psutil.Process(int(v)),
                    upsmon_processes.stdout.split()
                ),
                timeout=10
            )
            if alive:
                for pid in map(int, upsmon_processes.stdout.split()):
                    with contextlib.suppress(ProcessLookupError):
                        os.kill(pid, signal.SIGKILL)

    async def after_stop(self):
        if await self.middleware.call("service.started", "collectd"):
            asyncio.ensure_future(self.middleware.call("service.restart", "collectd"))
