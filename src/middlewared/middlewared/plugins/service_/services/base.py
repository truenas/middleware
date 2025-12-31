import asyncio
import contextlib
import logging
import types

# NOTE: We prefer to minimize third-party dependencies in critical service management code.
# However, jeepney was chosen for D-Bus communication because:
#   1. Pure Python implementation (no C extensions or Cython)
#   2. No transitive third-party dependencies
#   3. Verified under stress testing to be free of memory leaks
from jeepney import DBusAddress, new_method_call
from jeepney.bus_messages import message_bus, MatchRule
from jeepney.io.asyncio import open_dbus_router, Proxy
from jeepney.wrappers import unwrap_msg
from systemd import journal

from .base_interface import ServiceInterface, IdentifiableServiceInterface
from .base_state import ServiceState

logger = logging.getLogger(__name__)

_UNIT_SUFFIXES = (
    ".service",
    ".socket",
    ".target",
    ".mount",
    ".timer",
    ".path",
    ".slice",
    ".scope",
    ".swap",
    ".device",
)

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

_SYSTEMD_MANAGER = DBusAddress(
    "/org/freedesktop/systemd1",
    bus_name="org.freedesktop.systemd1",
    interface="org.freedesktop.systemd1.Manager",
)

_VERB_TO_ACTION = types.MappingProxyType(
    {
        "start": "Start",
        "stop": "Stop",
        "restart": "Restart",
        "reload": "Reload",
    }
)


async def _load_unit_path(router, service_name: str) -> str:
    """Load a systemd unit and return its D-Bus object path."""
    msg = new_method_call(_SYSTEMD_MANAGER, "LoadUnit", "s", (service_name,))
    reply = await router.send_and_get_reply(msg)
    return unwrap_msg(reply)[0]


async def _get_unit_property(router, unit_path: str, interface: str, prop: str):
    """Get a property from a systemd unit via D-Bus."""
    props = DBusAddress(
        unit_path,
        bus_name="org.freedesktop.systemd1",
        interface="org.freedesktop.DBus.Properties",
    )
    msg = new_method_call(props, "Get", "ss", (interface, prop))
    reply = await router.send_and_get_reply(msg)
    return unwrap_msg(reply)[0][1]


async def _verify_service_started(
    router, unit_path: str, service_name: str, action: str
) -> None:
    """
    Verify service is running after Start/Restart, log warnings if not.

    NOTE: There is an inherent race condition with D-Bus service management.
    Services that crash very quickly after starting (e.g., nut-server.service
    crashes in ~50ms due to missing UPS configuration) may appear as "active"
    at verification time, then crash milliseconds later. This is unavoidable
    without adding arbitrary sleeps, which would slow all service operations
    and still not guarantee detection. This matches systemctl behavior, which
    also does not wait to verify services stay running.
    """
    state = await _get_unit_property(
        router, unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
    )
    substate = await _get_unit_property(
        router, unit_path, "org.freedesktop.systemd1.Unit", "SubState"
    )

    if substate in ("auto-restart", "auto-restart-queued"):
        logger.warning("%s %s: service is crash-looping", service_name, action)
        return

    if state in ("active", "activating"):
        return

    conditions = await _get_unit_property(
        router, unit_path, "org.freedesktop.systemd1.Unit", "Conditions"
    )
    failed = [f"{c[0]}={c[3]}" for c in conditions if c[4] < 0]
    if failed:
        logger.warning(
            "%s %s skipped due to unmet conditions: %s",
            service_name,
            action,
            ", ".join(failed),
        )
        return

    if state == "failed":
        result = await _get_unit_property(
            router, unit_path, "org.freedesktop.systemd1.Service", "Result"
        )
        logger.warning("%s %s failed: %s", service_name, action, result)
    else:
        logger.warning("%s %s completed but service is %s", service_name, action, state)


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
        unit_path = await _load_unit_path(router, service_name)

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
        return unwrap_msg(reply)[0]


async def call_unit_action_and_wait(
    service_name: str | bytes, action: str, timeout: float = 10.0
) -> None:
    """
    Call a unit action and wait for job completion via D-Bus signals.

    Subscribes to JobRemoved signals before calling the action to avoid
    race conditions where the job completes before we start listening.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')
        action: The action to perform (Start, Stop, Restart, Reload)
        timeout: Maximum time to wait for job completion in seconds
    """
    if isinstance(service_name, bytes):
        service_name = service_name.decode()

    async with open_dbus_router(bus="SYSTEM") as router:
        await Proxy(message_bus, router).AddMatch(_JOB_REMOVED_SUBSCRIPTION_RULE)

        with router.filter(_JOB_REMOVED_FILTER_RULE) as queue:
            unit_path = await _load_unit_path(router, service_name)

            unit = DBusAddress(
                unit_path,
                bus_name="org.freedesktop.systemd1",
                interface="org.freedesktop.systemd1.Unit",
            )

            msg = new_method_call(unit, action, "s", ("replace",))
            reply = await router.send_and_get_reply(msg)
            job_path = unwrap_msg(reply)[0]

            try:
                async with asyncio.timeout(timeout):
                    while True:
                        msg = await queue.get()
                        if msg.body[1] == job_path:
                            result = msg.body[3]
                            if result != "done":
                                logger.warning(
                                    "%s %s job finished with result: %s",
                                    service_name,
                                    action,
                                    result,
                                )
                                return

                            if action in ("Start", "Restart"):
                                await _verify_service_started(
                                    router, unit_path, service_name, action
                                )
                            return
            except TimeoutError:
                # Timeout expired before our job's signal arrived. This is unlikely
                # but could happen if many other jobs complete during the wait period.
                pass


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
        await call_unit_action_and_wait(service_name, action, timeout)

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
    """Perform a systemd unit action via D-Bus."""
    action = _VERB_TO_ACTION.get(verb)
    if action is None:
        raise ValueError(f"Unsupported systemd verb: {verb}")

    # D-Bus LoadUnit requires full unit name with suffix
    if not unit.endswith(_UNIT_SUFFIXES):
        unit = f"{unit}.service"

    await call_unit_action_and_wait(unit, action)
