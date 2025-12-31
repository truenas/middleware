import asyncio
import contextlib
import logging
import subprocess

# NOTE: We prefer to minimize third-party dependencies in critical service management code.
# However, jeepney was chosen for D-Bus communication because:
#   1. Pure Python implementation (no C extensions or Cython)
#   2. No transitive third-party dependencies
#   3. Verified under stress testing to be free of memory leaks
from jeepney import DBusAddress, new_method_call
from jeepney.bus_messages import message_bus, MatchRule
from jeepney.io.asyncio import open_dbus_router, Proxy
from systemd import journal

from middlewared.utils import run

from .base_interface import ServiceInterface, IdentifiableServiceInterface
from .base_state import ServiceState

logger = logging.getLogger(__name__)

# D-Bus AddMatch rule includes sender for daemon filtering
_JOB_REMOVED_SUBSCRIPTION_RULE = MatchRule(
    type="signal",
    sender="org.freedesktop.systemd1",
    interface="org.freedesktop.systemd1.Manager",
    member="JobRemoved",
    path="/org/freedesktop/systemd1",
)

# Local filter rule omits sender (signal contains unique name, not well-known name)
_JOB_REMOVED_FILTER_RULE = MatchRule(
    type="signal",
    interface="org.freedesktop.systemd1.Manager",
    member="JobRemoved",
    path="/org/freedesktop/systemd1",
)


@contextlib.asynccontextmanager
async def open_unit(service_name: str | bytes):
    """
    Async context manager for accessing a systemd unit via D-Bus.

    Yields:
        Tuple of (router, unit_path, props_address) where:
        - router: The jeepney D-Bus router for sending messages
        - unit_path: The D-Bus object path for the unit
        - props: DBusAddress for accessing unit properties
    """
    if isinstance(service_name, bytes):
        service_name = service_name.decode()

    async with open_dbus_router(bus="SYSTEM") as router:
        manager = DBusAddress(
            "/org/freedesktop/systemd1",
            bus_name="org.freedesktop.systemd1",
            interface="org.freedesktop.systemd1.Manager",
        )

        msg = new_method_call(manager, "LoadUnit", "s", (service_name,))
        reply = await router.send_and_get_reply(msg)
        unit_path = reply.body[0]

        props = DBusAddress(
            unit_path,
            bus_name="org.freedesktop.systemd1",
            interface="org.freedesktop.DBus.Properties",
        )

        yield router, unit_path, props


async def get_inactive_exit_timestamp(service_name: str | bytes) -> int:
    """
    Get InactiveExitTimestampMonotonic for a systemd service via D-Bus.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')

    Returns:
        Timestamp in microseconds
    """
    async with open_unit(service_name) as (router, unit_path, props):
        msg = new_method_call(
            props,
            "Get",
            "ss",
            ("org.freedesktop.systemd1.Unit", "InactiveExitTimestampMonotonic"),
        )
        reply = await router.send_and_get_reply(msg)
        return reply.body[0][1]


async def get_service_state(service_name: str | bytes) -> tuple[bytes, int]:
    """
    Get ActiveState and MainPID for a systemd service via D-Bus.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')

    Returns:
        Tuple of (active_state as bytes, main_pid as int)
    """
    async with open_unit(service_name) as (router, unit_path, props):
        # Get ActiveState from Unit interface
        msg = new_method_call(
            props, "Get", "ss", ("org.freedesktop.systemd1.Unit", "ActiveState")
        )
        reply = await router.send_and_get_reply(msg)
        active_state = reply.body[0][1].encode()

        # Get MainPID from Service interface
        msg = new_method_call(
            props, "Get", "ss", ("org.freedesktop.systemd1.Service", "MainPID")
        )
        reply = await router.send_and_get_reply(msg)
        main_pid = reply.body[0][1]

        return active_state, main_pid


async def get_unit_active_state(service_name: str | bytes) -> str:
    """
    Get ActiveState for a systemd service via D-Bus.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')

    Returns:
        Active state as string (e.g., "active", "inactive", "activating")
    """
    async with open_unit(service_name) as (router, unit_path, props):
        msg = new_method_call(
            props, "Get", "ss", ("org.freedesktop.systemd1.Unit", "ActiveState")
        )
        reply = await router.send_and_get_reply(msg)
        return reply.body[0][1]


async def call_unit_action(service_name: str | bytes, action: str) -> str:
    """
    Call a unit action (Start, Stop, Restart, Reload) and return the job path.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')
        action: The action to perform (Start, Stop, Restart, Reload)

    Returns:
        Job object path
    """
    async with open_unit(service_name) as (router, unit_path, props):
        unit = DBusAddress(
            unit_path,
            bus_name="org.freedesktop.systemd1",
            interface="org.freedesktop.systemd1.Unit",
        )

        msg = new_method_call(unit, action, "s", ("replace",))
        reply = await router.send_and_get_reply(msg)
        return reply.body[0]


class SimpleService(ServiceInterface, IdentifiableServiceInterface):
    systemd_unit = NotImplemented
    systemd_async_start = False
    systemd_unit_timeout = 5

    async def systemd_extra_units(self):
        return []

    async def get_state(self):
        unit_name = self._get_systemd_unit_name()
        state, main_pid = await get_service_state(unit_name)
        if state == b"active" or (self.systemd_async_start and state == b"activating"):
            return ServiceState(True, list(filter(None, [main_pid])))
        else:
            return ServiceState(False, [])

    async def get_unit_state(self):
        unit_name = self._get_systemd_unit_name()
        return await get_unit_active_state(unit_name)

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
        unit_name = self._get_systemd_unit_name()
        monotonic_timestamp = await get_inactive_exit_timestamp(unit_name)
        return await self.middleware.run_in_thread(
            self._unit_failure_logs, monotonic_timestamp
        )

    def _get_systemd_unit_name(self):
        return f"{self.systemd_unit}.service"

    async def _unit_action(self, action, wait=True):
        unit_name = self._get_systemd_unit_name()
        if wait:
            await self._call_unit_action_and_wait(
                unit_name, action, self.systemd_unit_timeout
            )
        else:
            await call_unit_action(unit_name, action)

    async def _call_unit_action_and_wait(self, service_name, action, timeout):
        """
        Call a unit action and wait for job completion via D-Bus signals.

        Subscribes to JobRemoved signals before calling the action to avoid
        race conditions where the job completes before we start listening.
        """
        async with open_dbus_router(bus="SYSTEM") as router:
            await Proxy(message_bus, router).AddMatch(_JOB_REMOVED_SUBSCRIPTION_RULE)

            with router.filter(_JOB_REMOVED_FILTER_RULE) as queue:
                manager = DBusAddress(
                    "/org/freedesktop/systemd1",
                    bus_name="org.freedesktop.systemd1",
                    interface="org.freedesktop.systemd1.Manager",
                )

                msg = new_method_call(manager, "LoadUnit", "s", (service_name,))
                reply = await router.send_and_get_reply(msg)
                unit_path = reply.body[0]

                unit = DBusAddress(
                    unit_path,
                    bus_name="org.freedesktop.systemd1",
                    interface="org.freedesktop.systemd1.Unit",
                )

                msg = new_method_call(unit, action, "s", ("replace",))
                reply = await router.send_and_get_reply(msg)
                job_path = reply.body[0]

                try:
                    while True:
                        msg = await asyncio.wait_for(queue.get(), timeout)
                        if msg.body[1] == job_path:
                            return
                except asyncio.TimeoutError:
                    pass

    async def _systemd_unit(self, unit, verb):
        await systemd_unit(unit, verb)

    def _unit_failure_logs(self, monotonic_timestamp):
        unit_name = self._get_systemd_unit_name().encode()

        with journal.Reader() as j:
            j.seek_monotonic(monotonic_timestamp / 1e6)

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

            return "\n".join(
                [
                    f"{record['__REALTIME_TIMESTAMP'].strftime('%b %d %H:%M:%S')} "
                    f"{record.get('SYSLOG_IDENTIFIER')}[{record.get('_PID', 0)}]: {record['MESSAGE']}"
                    for record in j
                ]
            )


async def systemd_unit(unit, verb):
    result = await run(
        "systemctl", verb, unit, check=False, encoding="utf-8", stderr=subprocess.STDOUT
    )
    if result.returncode != 0:
        logger.warning(
            "%s %s failed with code %d: %r",
            unit,
            verb,
            result.returncode,
            result.stdout,
        )

    return result
