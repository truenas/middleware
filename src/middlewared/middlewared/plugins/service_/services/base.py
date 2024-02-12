import logging
import select
import subprocess

from pystemd.base import SDObject
from pystemd.dbusexc import DBusUnknownObjectError
from pystemd.dbuslib import DBus
from pystemd.systemd1 import Unit
from systemd import journal

from middlewared.utils import run

from .base_interface import ServiceInterface, IdentifiableServiceInterface
from .base_state import ServiceState

logger = logging.getLogger(__name__)


class Job(SDObject):
    def __init__(self, job, bus=None, _autoload=False):
        super().__init__(
            destination=b"org.freedesktop.systemd1",
            path=job,
            bus=bus,
            _autoload=_autoload,
        )


class SimpleService(ServiceInterface, IdentifiableServiceInterface):
    systemd_unit = NotImplemented
    systemd_async_start = False
    systemd_unit_timeout = 5

    async def systemd_extra_units(self):
        return []

    async def get_state(self):
        return await self.middleware.run_in_thread(self._get_state_sync)

    def _get_state_sync(self):
        unit = self._get_systemd_unit()

        state = unit.Unit.ActiveState
        if state == b"active" or (self.systemd_async_start and state == b"activating"):
            return ServiceState(True, list(filter(None, [unit.MainPID])))
        else:
            return ServiceState(False, [])

    async def get_unit_state(self):
        return await self.middleware.run_in_thread(self._get_unit_state_sync)

    def _get_unit_state_sync(self):
        unit = self._get_systemd_unit()
        state = unit.Unit.ActiveState
        return state.decode("utf-8")

    async def start(self):
        await self._unit_action("Start")

    async def stop(self):
        await self._unit_action("Stop")

    async def restart(self):
        await self._unit_action("Restart")

    async def reload(self):
        await self._unit_action("Reload")

    async def identify(self, procname):
        pass

    async def failure_logs(self):
        return await self.middleware.run_in_thread(self._unit_failure_logs)

    def _get_systemd_unit(self):
        unit = Unit(self._get_systemd_unit_name())
        unit.load()
        return unit

    def _get_systemd_unit_name(self):
        return f"{self.systemd_unit}.service".encode()

    async def _unit_action(self, action, wait=True):
        return await self.middleware.run_in_thread(self._unit_action_sync, action, wait, self.systemd_unit_timeout)

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

    def _unit_failure_logs(self):
        unit = self._get_systemd_unit()
        unit_name = self._get_systemd_unit_name()

        j = journal.Reader()
        j.seek_monotonic(unit.Unit.InactiveExitTimestampMonotonic / 1e6)

        # copied from `https://github.com/systemd/systemd/blob/main/src/shared/logs-show.c`,
        # `add_matches_for_unit` function

        # Look for messages from the service itself
        j.add_match(_SYSTEMD_UNIT=unit_name)

        # Look for coredumps of the service
        j.add_disjunction()
        j.add_match(MESSAGE_ID=b"fc2e22bc6ee647b6b90729ab34a250b1")
        j.add_match(_UID=0)
        j.add_match(COREDUMP_UNIT=unit_name)

        # Look for messages from PID 1 about this service
        j.add_disjunction()
        j.add_match(_PID=1)
        j.add_match(UNIT=unit_name)

        # Look for messages from authorized daemons about this service
        j.add_disjunction()
        j.add_match(_UID=0)
        j.add_match(OBJECT_SYSTEMD_UNIT=unit_name)

        return "\n".join([
            f"{record['__REALTIME_TIMESTAMP'].strftime('%b %d %H:%M:%S')} "
            f"{record.get('SYSLOG_IDENTIFIER')}[{record.get('_PID', 0)}]: {record['MESSAGE']}"
            for record in j
        ])


async def systemd_unit(unit, verb):
    result = await run("systemctl", verb, unit, check=False, encoding="utf-8", stderr=subprocess.STDOUT)
    if result.returncode != 0:
        logger.warning("%s %s failed with code %d: %r", unit, verb, result.returncode, result.stdout)

    return result
