import asyncio
import contextlib
import logging
import time
import types

# NOTE: We prefer to minimize third-party dependencies in critical service management code.
# However, jeepney was chosen for D-Bus communication because:
#   1. Pure Python implementation (no C extensions or Cython)
#   2. No transitive third-party dependencies
#   3. Verified under stress testing to be free of memory leaks
from jeepney import DBusAddress, new_method_call
from jeepney.bus_messages import message_bus, MatchRule
from jeepney.io.asyncio import open_dbus_router, Proxy
from jeepney.wrappers import DBusErrorResponse, unwrap_msg

from middlewared.utils.journal import (
    format_journal_record,
    monotonic_to_realtime_since,
    query_journal,
)

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

# systemd's compiled-in default timeout (90 seconds)
_SYSTEMD_DEFAULT_TIMEOUT_SEC = 90.0

# Buffer added on top of systemd's timeout to avoid racing it
_TIMEOUT_BUFFER_SEC = 5.0

# systemd's USEC_INFINITY means "no timeout"
_USEC_INFINITY = 2**64 - 1

# Mapping from unit action to the relevant timeout property name(s)
# on the org.freedesktop.systemd1.Service interface.
_ACTION_TIMEOUT_PROPERTIES = types.MappingProxyType({
    "Start": ("TimeoutStartUSec",),
    "Reload": ("TimeoutStartUSec",),
    "Stop": ("TimeoutStopUSec",),
    "Restart": ("TimeoutStopUSec", "TimeoutStartUSec"),
})


async def _get_unit_timeout(
    router, unit_path: str, service_name: str, action: str
) -> float:
    """
    Query systemd via D-Bus for the effective timeout of a unit action.

    For .service units, reads TimeoutStartUSec / TimeoutStopUSec from the
    org.freedesktop.systemd1.Service interface. For other unit types or on
    error, falls back to the systemd compiled-in default (90s).

    Returns the timeout in seconds with a buffer added to avoid racing systemd.
    """
    props = _ACTION_TIMEOUT_PROPERTIES.get(action)
    if props is None:
        return _SYSTEMD_DEFAULT_TIMEOUT_SEC + _TIMEOUT_BUFFER_SEC

    # Only .service units expose TimeoutStart/StopUSec on the Service interface.
    if not service_name.endswith(".service"):
        return _SYSTEMD_DEFAULT_TIMEOUT_SEC + _TIMEOUT_BUFFER_SEC

    total_usec = 0
    try:
        for prop_name in props:
            usec = await _get_unit_property(
                router, unit_path, "org.freedesktop.systemd1.Service", prop_name
            )
            if usec >= _USEC_INFINITY:
                total_usec += int(_SYSTEMD_DEFAULT_TIMEOUT_SEC * 1_000_000)
            else:
                total_usec += usec
    except Exception:
        logger.debug(
            "%s: failed to query %s timeout from D-Bus, using default",
            service_name,
            action,
            exc_info=True,
        )
        return _SYSTEMD_DEFAULT_TIMEOUT_SEC + _TIMEOUT_BUFFER_SEC

    return total_usec / 1_000_000 + _TIMEOUT_BUFFER_SEC


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


async def _verify_service_running(
    router, unit_path: str, service_name: str, action: str
) -> None:
    """
    Verify service is in expected running state after action, log warnings if not.

    For Start/Restart: expects "active" or "activating"
    For Reload: expects "active" or "reloading"

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

    # Determine acceptable states based on action
    if action == "Reload":
        # For reload, service should be active or still reloading
        acceptable_states = ("active", "reloading")
    else:
        # For start/restart, service should be active or still activating
        acceptable_states = ("active", "activating")

    if state in acceptable_states:
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


def _normalize_unit_name(service_name: str | bytes) -> str:
    """Decode bytes and ensure unit name has a suffix (defaults to .service)."""
    if isinstance(service_name, bytes):
        service_name = service_name.decode()
    if not service_name.endswith(_UNIT_SUFFIXES):
        service_name = f"{service_name}.service"
    return service_name


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
    service_name = _normalize_unit_name(service_name)

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


async def get_unit_file_state(service_name: str | bytes) -> str:
    """
    Get UnitFileState for a systemd unit via D-Bus.

    Uses the Manager.GetUnitFileState method rather than loading the unit and
    reading its property, because LoadUnit creates stub units for non-existent
    services (returning an empty string) instead of reporting "not-found".

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')

    Returns:
        Unit file state as string (e.g., "enabled", "disabled", "static", "masked", "not-found")
    """
    service_name = _normalize_unit_name(service_name)
    async with open_dbus_router(bus="SYSTEM") as router:
        try:
            msg = new_method_call(_SYSTEMD_MANAGER, "GetUnitFileState", "s", (service_name,))
            reply = await router.send_and_get_reply(msg)
            return unwrap_msg(reply)[0]
        except DBusErrorResponse as e:
            if e.name == "org.freedesktop.DBus.Error.FileNotFound":
                return "not-found"
            raise


async def set_unit_file_state(service_name: str | bytes, enabled: bool) -> None:
    """
    Enable or disable a systemd unit file via D-Bus.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')
        enabled: True to enable, False to disable
    """
    service_name = _normalize_unit_name(service_name)

    async with open_dbus_router(bus="SYSTEM") as router:
        if enabled:
            msg = new_method_call(
                _SYSTEMD_MANAGER, "EnableUnitFiles", "asbb", ([service_name], False, True)
            )
        else:
            msg = new_method_call(
                _SYSTEMD_MANAGER, "DisableUnitFiles", "asb", ([service_name], False)
            )
        await router.send_and_get_reply(msg)


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


async def _stop_unit_and_wait_for_exit(
    router,
    unit_path: str,
    service_name: str,
    timeout: float,
    start_time: float,
    timeout_is_explicit: bool = False,
) -> None:
    """
    Stop a systemd unit and wait for all processes to exit.

    Issues a Stop command, waits for systemd to send SIGTERM (JobRemoved signal),
    then polls until MainPID=0 or ActiveState=inactive to ensure all processes
    have fully exited.

    This prevents race conditions where services with slow shutdown (e.g., netdata
    flushing databases) still have open file handles when subsequent operations
    (umount, zfs destroy) are attempted.

    Args:
        router: Open D-Bus router
        unit_path: D-Bus object path for the unit
        service_name: Service name for logging
        timeout: Maximum time to wait for job completion
        start_time: Start time from time.monotonic() for elapsed calculation
        timeout_is_explicit: True if the caller provided the timeout (log at DEBUG),
                             False if auto-detected from systemd (log at WARNING)
    """
    # Only service units have MainPID property. Socket, target, timer, etc.
    # units don't have the org.freedesktop.systemd1.Service interface.
    is_service_unit = service_name.endswith(".service")
    with router.filter(_JOB_REMOVED_FILTER_RULE) as job_queue:
        # Issue the stop action
        unit = DBusAddress(
            unit_path,
            bus_name="org.freedesktop.systemd1",
            interface="org.freedesktop.systemd1.Unit",
        )

        msg = new_method_call(unit, "Stop", "s", ("replace",))
        reply = await router.send_and_get_reply(msg)
        job_path = unwrap_msg(reply)[0]

        # Wait for JobRemoved
        try:
            async with asyncio.timeout(timeout):
                while True:
                    msg = await job_queue.get()
                    if msg.body[1] == job_path:
                        result = msg.body[3]
                        if result != "done":
                            logger.warning(
                                "%s Stop job finished with result: %s",
                                service_name,
                                result,
                            )
                        break
        except TimeoutError:
            if timeout_is_explicit:
                logger.debug(
                    "%s Stop: stopped waiting after %.1fs (job still running)",
                    service_name,
                    timeout,
                )
            else:
                logger.warning(
                    "%s Stop job timed out after %.1fs, continuing to wait for process exit",
                    service_name,
                    timeout,
                )

        # Wait for processes to actually exit by polling state
        elapsed = time.monotonic() - start_time
        timeout_remaining = max(5.0, timeout - elapsed)
        poll_deadline = time.monotonic() + timeout_remaining
        check_interval = 0.1  # Check every 100ms

        while time.monotonic() < poll_deadline:
            try:
                active_state = await _get_unit_property(
                    router,
                    unit_path,
                    "org.freedesktop.systemd1.Unit",
                    "ActiveState",
                )

                # For service units, also check MainPID to ensure process exited
                main_pid = 0
                if is_service_unit:
                    main_pid = await _get_unit_property(
                        router, unit_path, "org.freedesktop.systemd1.Service", "MainPID"
                    )

                if main_pid == 0 or active_state == "inactive":
                    # Unit fully stopped - only log if abnormally slow
                    elapsed_total = time.monotonic() - start_time
                    if elapsed_total > 3.0:
                        logger.warning(
                            "%s took %.2fs to stop (abnormally slow)",
                            service_name,
                            elapsed_total,
                        )
                    return

                # Not stopped yet, wait before next check
                await asyncio.sleep(check_interval)
            except Exception:
                logger.exception("%s: Error checking status", service_name)
                await asyncio.sleep(check_interval)

        # Timeout - check final state
        try:
            final_state = await _get_unit_property(
                router, unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
            )
            if is_service_unit:
                final_main_pid = await _get_unit_property(
                    router, unit_path, "org.freedesktop.systemd1.Service", "MainPID"
                )
                logger.warning(
                    "Timeout waiting for %s processes to exit after %.1fs (final: MainPID=%s, ActiveState=%s)",
                    service_name,
                    timeout_remaining,
                    final_main_pid,
                    final_state,
                )
            else:
                logger.warning(
                    "Timeout waiting for %s to stop after %.1fs (final: ActiveState=%s)",
                    service_name,
                    timeout_remaining,
                    final_state,
                )
        except Exception:
            logger.exception(
                "Timeout waiting for %s processes to exit after %.1fs (unable to check final state)",
                service_name,
                timeout_remaining,
            )


async def call_unit_action_and_wait(
    service_name: str | bytes, action: str, timeout: float | None = None
) -> None:
    """
    Call a unit action and wait for job completion via D-Bus signals.

    Subscribes to JobRemoved signals before calling the action to avoid
    race conditions where the job completes before we start listening.

    For Stop actions, delegates to _stop_unit_and_wait_for_exit() which waits
    for processes to actually exit by polling the service state.

    Args:
        service_name: The systemd unit name (e.g., 'smbd.service' or b'smbd.service')
        action: The action to perform (Start, Stop, Restart, Reload)
        timeout: Maximum time to wait for job completion in seconds.
                 If None, auto-detects from the unit's systemd timeout
                 properties via D-Bus, with a small buffer.
    """
    service_name = _normalize_unit_name(service_name)
    timeout_is_explicit = timeout is not None

    start_time = time.monotonic()

    async with open_dbus_router(bus="SYSTEM") as router:
        await Proxy(message_bus, router).AddMatch(_JOB_REMOVED_SUBSCRIPTION_RULE)

        unit_path = await _load_unit_path(router, service_name)

        if not timeout_is_explicit:
            timeout = await _get_unit_timeout(router, unit_path, service_name, action)

        if action == "Stop":
            await _stop_unit_and_wait_for_exit(
                router, unit_path, service_name, timeout, start_time,
                timeout_is_explicit,
            )
        else:
            # For non-Stop actions, use original flow
            with router.filter(_JOB_REMOVED_FILTER_RULE) as queue:
                # Issue the action
                unit = DBusAddress(
                    unit_path,
                    bus_name="org.freedesktop.systemd1",
                    interface="org.freedesktop.systemd1.Unit",
                )

                msg = new_method_call(unit, action, "s", ("replace",))
                reply = await router.send_and_get_reply(msg)
                job_path = unwrap_msg(reply)[0]

                # Wait for JobRemoved
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
                                break
                except TimeoutError:
                    if timeout_is_explicit:
                        logger.debug(
                            "%s %s: stopped waiting after %.1fs (job still running)",
                            service_name,
                            action,
                            timeout,
                        )
                    else:
                        logger.warning(
                            "%s %s job timed out after %.1fs",
                            service_name,
                            action,
                            timeout,
                        )
                    return

            # Verify service is running
            await _verify_service_running(router, unit_path, service_name, action)


class SimpleService(ServiceInterface, IdentifiableServiceInterface):
    systemd_unit = NotImplemented
    systemd_async_start = False

    async def systemd_extra_units(self):
        return []

    async def get_state(self):
        unit_name = self._get_systemd_unit_name()
        state, main_pid = await get_service_state(unit_name)
        if (
            state == b"active"
            or (self.systemd_async_start and state == b"activating")
            or state == b"reloading"
        ):
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
            await self._call_unit_action_and_wait(unit_name, action)
        else:
            await call_unit_action(unit_name, action)

    async def _call_unit_action_and_wait(self, service_name, action, timeout=None):
        await call_unit_action_and_wait(service_name, action, timeout)

    async def _systemd_unit(self, unit, verb):
        await systemd_unit(unit, verb)

    def _unit_failure_logs(self, monotonic_timestamp):
        unit_name = self._get_systemd_unit_name()
        since = monotonic_to_realtime_since(monotonic_timestamp)

        # Match logic from systemd's add_matches_for_unit
        # (https://github.com/systemd/systemd/blob/main/src/shared/logs-show.c)
        # Using + for OR (disjunction) between match groups
        match_args = [
            # Match group 1: messages from the service itself
            f"_SYSTEMD_UNIT={unit_name}",
            # OR
            "+",
            # Match group 2: coredumps of the service
            "MESSAGE_ID=fc2e22bc6ee647b6b90729ab34a250b1",
            "_UID=0",
            f"COREDUMP_UNIT={unit_name}",
            # OR
            "+",
            # Match group 3: messages from PID 1 about this service
            "_PID=1",
            f"UNIT={unit_name}",
            # OR
            "+",
            # Match group 4: messages from authorized daemons about this service
            "_UID=0",
            f"OBJECT_SYSTEMD_UNIT={unit_name}",
        ]

        records = query_journal(match_args, since=since)
        return "\n".join(format_journal_record(r) for r in records)


async def systemd_unit(unit, verb):
    """Perform a systemd unit action via D-Bus."""
    action = _VERB_TO_ACTION.get(verb)
    if action is None:
        raise ValueError(f"Unsupported systemd verb: {verb}")

    await call_unit_action_and_wait(_normalize_unit_name(unit), action)
