import logging
import select
import subprocess

from middlewared.utils import run
from middlewared.utils.osc import IS_LINUX

from .base_state import ServiceState

logger = logging.getLogger(__name__)

if IS_LINUX:
    from pystemd.base import SDObject
    from pystemd.dbusexc import DBusUnknownObjectError
    from pystemd.dbuslib import DBus
    from pystemd.systemd1 import Unit

    class Job(SDObject):
        def __init__(self, job, bus=None, _autoload=False):
            super().__init__(
                destination=b"org.freedesktop.systemd1",
                path=job,
                bus=bus,
                _autoload=_autoload,
            )


class SimpleServiceLinux:
    systemd_unit = NotImplemented
    systemd_async_start = False

    async def systemd_extra_units(self):
        return []

    async def _get_state_linux(self):
        return await self.middleware.run_in_thread(self._get_state_linux_sync)

    def _get_state_linux_sync(self):
        unit = self._get_systemd_unit()

        state = unit.Unit.ActiveState
        if state == b"active" or (self.systemd_async_start and state == b"activating"):
            return ServiceState(True, list(filter(None, [unit.MainPID])))

        else:
            return ServiceState(False, [])

    async def _start_linux(self):
        await self._unit_action("Start")

    async def _stop_linux(self):
        await self._unit_action("Stop")

    async def _restart_linux(self):
        await self._unit_action("Restart")

    async def _reload_linux(self):
        await self._unit_action("Reload")

    async def _identify_linux(self, procname):
        pass

    def _get_systemd_unit(self):
        unit = Unit(f"{self.systemd_unit}.service".encode())
        unit.load()
        return unit

    async def _unit_action(self, action, wait=True, timeout=5):
        return await self.middleware.run_in_thread(self._unit_action_sync, action, wait, timeout)

    def _unit_action_sync(self, action, wait, timeout):
        unit = self._get_systemd_unit()
        job = getattr(unit.Unit, action)(b"replace")

        if wait:
            with DBus() as bus:
                done = False

                def callback(msg, error=None, userdata=None):
                    nonlocal done

                    msg.process_reply(True)

                    if msg.body[1] == job:
                        done = True

                bus.match_signal(
                    b"org.freedesktop.systemd1",
                    b"/org/freedesktop/systemd1",
                    b"org.freedesktop.systemd1.Manager",
                    b"JobRemoved",
                    callback,
                    None,
                )

                job_object = Job(job, bus)
                try:
                    job_object.load()
                except DBusUnknownObjectError:
                    # Job has already completed
                    return

                fd = bus.get_fd()
                while True:
                    fds = select.select([fd], [], [], timeout)
                    if not any(fds):
                        break

                    bus.process()

                    if done:
                        break

    async def _systemd_unit(self, unit, verb):
        await systemd_unit(unit, verb)


async def systemd_unit(unit, verb):
    result = await run("systemctl", verb, unit, check=False, encoding="utf-8", stderr=subprocess.STDOUT)
    if result.returncode != 0:
        logger.warning("%s %s failed with code %d: %r", unit, verb, result.returncode, result.stdout)

    return result
