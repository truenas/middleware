import asyncio
from dataclasses import dataclass, field
import logging
import time
import types

# NOTE: We prefer to minimize third-party dependencies in critical service management code.
# However, jeepney was chosen for D-Bus communication because:
#   1. Pure Python implementation (no C extensions or Cython)
#   2. No transitive third-party dependencies
#   3. Verified under stress testing to be free of memory leaks
from jeepney import DBusAddress, new_method_call
from jeepney.bus_messages import MatchRule, message_bus
from jeepney.io.asyncio import DBusConnection, DBusRouter, Proxy, open_dbus_connection
from jeepney.wrappers import DBusErrorResponse, unwrap_msg

__all__ = ("ServiceActionError", "system_dbus")


class ServiceActionError(Exception):
    """Service not in expected state after a systemd action."""

    def __init__(self, unit, action, detail):
        self.unit = unit
        self.action = action
        self.detail = detail
        super().__init__(unit, action, detail)

    def __str__(self):
        return f"{self.unit} {self.action}: {self.detail}"


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
_PHASE1_POLL_INTERVAL = 0.2

# Mapping from unit action to the relevant timeout property name(s)
# on the org.freedesktop.systemd1.Service interface.
_ACTION_TIMEOUT_PROPERTIES = types.MappingProxyType(
    {
        "Start": ("TimeoutStartUSec",),
        "Reload": ("TimeoutStartUSec",),
        "Stop": ("TimeoutStopUSec",),
        "Restart": ("TimeoutStopUSec", "TimeoutStartUSec"),
    }
)


@dataclass(slots=True)
class CachedSystemDBusRouter:
    """Cached D-Bus router for the SYSTEM bus.

    Fixes upstream issues in jeepney's open_dbus_router:
    1. DBusRouter.__init__ eagerly fires a receiver task via
       asyncio.create_task — we defer construction to first acquire.
    2. open_dbus_router.__aexit__ doesn't wrap conn.close() in
       try/finally — a router teardown exception leaks the socket.
    3. Every open_dbus_router() call opens a new connection + auth +
       Hello handshake — we reuse a single connection.
    4. Per-call routers produce orphaned background tasks that can
       trigger a self-deadlock on CPython's _global_shutdown_lock
       when the GC finalizes them inside ThreadPoolExecutor.submit().
       A single long-lived router eliminates this task churn.

    Reconnects automatically when the receiver task dies or when any
    unexpected error occurs during send (indicating a dead connection).
    DBusErrorResponse is excluded from reconnect since it indicates a
    valid D-Bus reply (the connection is healthy, systemd just returned
    an error).
    """

    _conn: DBusConnection | None = field(default=None, init=False)
    _router: DBusRouter | None = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    def _is_alive(self) -> bool:
        return self._router is not None and not self._router._rcv_task.done()

    async def _teardown(self) -> None:
        router, conn = self._router, self._conn
        self._router = self._conn = None
        if router is not None:
            try:
                await router.__aexit__(None, None, None)
            except Exception:
                logger.debug("D-Bus router teardown error", exc_info=True)
        if conn is not None:
            try:
                await conn.close()
            except Exception:
                logger.debug("D-Bus connection close error", exc_info=True)

    async def _ensure_router(self) -> DBusRouter:
        # Fast path — no lock needed when healthy
        if self._is_alive():
            return self._router
        async with self._lock:
            if not self._is_alive():
                await self._teardown()
                self._conn = await open_dbus_connection("SYSTEM")
                self._router = DBusRouter(self._conn)
                # Subscribe once per connection — reusing the same connection
                # means AddMatch rules accumulate and hit dbus-daemon's
                # max_match_rules_per_connection limit (default 512).
                await Proxy(message_bus, self._router).AddMatch(
                    _JOB_REMOVED_SUBSCRIPTION_RULE
                )
        return self._router

    async def _invalidate(self) -> None:
        """Force teardown so the next _ensure_router() reconnects."""
        async with self._lock:
            await self._teardown()

    async def _send(self, msg):
        """Send a message and return the reply, reconnecting on failure.

        Any error except DBusErrorResponse is treated as a potential
        connection problem — the cached router is torn down and a fresh
        connection is established for one retry.  DBusErrorResponse is a
        valid D-Bus reply (healthy connection) and is always propagated.
        """
        router = await self._ensure_router()
        try:
            return await router.send_and_get_reply(msg)
        except Exception as e:
            if isinstance(e, DBusErrorResponse):
                raise
            logger.debug("D-Bus send error, reconnecting", exc_info=True)
            await self._invalidate()
            router = await self._ensure_router()
            return await router.send_and_get_reply(msg)

    @staticmethod
    def _normalize_unit_name(service_name: str | bytes) -> str:
        """Decode bytes and ensure unit name has a suffix (defaults to .service)."""
        if isinstance(service_name, bytes):
            service_name = service_name.decode()
        if not service_name.endswith(_UNIT_SUFFIXES):
            service_name = f"{service_name}.service"
        return service_name

    async def _load_unit_path(self, service_name: str) -> str:
        """Load a systemd unit and return its D-Bus object path."""
        msg = new_method_call(_SYSTEMD_MANAGER, "LoadUnit", "s", (service_name,))
        reply = await self._send(msg)
        return unwrap_msg(reply)[0]

    async def _get_unit_property(self, unit_path: str, interface: str, prop: str):
        """Get a property from a systemd unit via D-Bus."""
        props = DBusAddress(
            unit_path,
            bus_name="org.freedesktop.systemd1",
            interface="org.freedesktop.DBus.Properties",
        )
        msg = new_method_call(props, "Get", "ss", (interface, prop))
        reply = await self._send(msg)
        return unwrap_msg(reply)[0][1]

    async def _get_unit_timeout(
        self, unit_path: str, service_name: str, action: str
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
                usec = await self._get_unit_property(
                    unit_path, "org.freedesktop.systemd1.Service", prop_name
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

    async def _verify_service_running(
        self, unit_path: str, service_name: str, action: str
    ) -> None:
        """
        Verify service is in expected running state after action.

        Raises ServiceActionError when the service is detected as:
        - crash-looping (SubState = auto-restart)
        - failed (ActiveState = failed)
        - in an unexpected state after the action

        Unmet conditions (systemd skipped the unit by design) are logged
        as warnings but do not raise, since the service was never attempted.

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
        state = await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
        )
        substate = await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Unit", "SubState"
        )

        if substate in ("auto-restart", "auto-restart-queued"):
            raise ServiceActionError(
                service_name, action, "service is crash-looping"
            )

        # Determine acceptable states based on action
        if action == "Reload":
            # For reload, service should be active or still reloading
            acceptable_states = ("active", "reloading")
        else:
            # For start/restart, service should be active or still activating
            acceptable_states = ("active", "activating")

        if state in acceptable_states:
            return

        # Oneshot services (e.g. nut-driver-enumerator) go to
        # ActiveState=inactive after successful completion — this is
        # normal and should not be treated as a failure.
        if state == "inactive" and action in ("Start", "Restart"):
            try:
                svc_type = await self._get_unit_property(
                    unit_path,
                    "org.freedesktop.systemd1.Service",
                    "Type",
                )
                if svc_type == "oneshot":
                    result = await self._get_unit_property(
                        unit_path,
                        "org.freedesktop.systemd1.Service",
                        "Result",
                    )
                    if result == "success":
                        return
            except Exception:
                pass

        conditions = await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Unit", "Conditions"
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
            result = await self._get_unit_property(
                unit_path, "org.freedesktop.systemd1.Service", "Result"
            )
            raise ServiceActionError(
                service_name, action, f"failed: {result}"
            )

        raise ServiceActionError(
            service_name, action, f"unexpected state: {state}"
        )

    @staticmethod
    async def _phase1_wait_for_job_removed(job_queue, job_path: str) -> str | None:
        """Return the Stop job result string once the matching JobRemoved signal arrives."""
        while True:
            msg = await job_queue.get()
            if msg.body[1] == job_path:
                return msg.body[3]

    async def _phase1_wait_for_inactive(self, unit_path: str) -> None:
        """Return when the unit reaches inactive or failed state."""
        while True:
            await asyncio.sleep(_PHASE1_POLL_INTERVAL)
            try:
                state = await self._get_unit_property(
                    unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
                )
                if state in ("inactive", "failed"):
                    return
            except Exception:
                pass

    async def _stop_unit_and_wait_for_exit(
        self,
        unit_path: str,
        service_name: str,
        timeout: float,
        start_time: float,
        timeout_is_explicit: bool = False,
    ) -> None:
        """
        Stop a systemd unit and wait for all processes to exit.

        Issues a Stop command then proceeds in two phases:

        Phase 1 — wait for the JobRemoved D-Bus signal that indicates systemd has
        finished processing the Stop job (i.e. SIGTERM / SIGKILL sent).

        Phase 2 — poll ActiveState (and MainPID for .service units) until the unit
        reaches inactive/failed state, ensuring all processes have fully exited.
        This prevents race conditions where services with slow shutdown (e.g., netdata
        flushing databases) still have open file handles when subsequent operations
        (umount, zfs destroy) are attempted.
        """
        # Only service units have MainPID property. Socket, target, timer, etc.
        # units don't have the org.freedesktop.systemd1.Service interface.
        is_service_unit = service_name.endswith(".service")

        # We need the raw router for filter() — _send() handles reconnect for
        # the initial Stop call, but once we're inside filter() we're committed
        # to this connection for signal delivery.
        router = await self._ensure_router()
        with router.filter(_JOB_REMOVED_FILTER_RULE) as job_queue:
            # Issue the stop action
            unit = DBusAddress(
                unit_path,
                bus_name="org.freedesktop.systemd1",
                interface="org.freedesktop.systemd1.Unit",
            )

            msg = new_method_call(unit, "Stop", "s", ("replace",))
            try:
                reply = await router.send_and_get_reply(msg)
            except Exception as e:
                if not isinstance(e, DBusErrorResponse):
                    # Connection died before we could send Stop — teardown and let
                    # the caller retry the whole operation.
                    await self._invalidate()
                raise
            job_path = unwrap_msg(reply)[0]

            # Phase 1: Wait for JobRemoved *or* for the unit to reach an inactive/failed
            # state — whichever comes first.  The concurrent poll handles the race where
            # systemd deactivates the unit as a dependency of another unit stopping before
            # our explicit Stop job fires its JobRemoved signal (e.g. virtlogd.socket
            # being torn down implicitly when libvirtd stops).
            job_task = asyncio.create_task(
                self._phase1_wait_for_job_removed(job_queue, job_path)
            )
            poll_task = asyncio.create_task(self._phase1_wait_for_inactive(unit_path))
            done, pending = await asyncio.wait(
                {job_task, poll_task},
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            for t in pending:
                t.cancel()
                try:
                    await t
                except (asyncio.CancelledError, Exception):
                    pass

            if poll_task in done:
                # Unit became inactive before JobRemoved arrived — return immediately,
                # skipping Phase 2 (there's nothing left to wait for).
                elapsed_total = time.monotonic() - start_time
                if elapsed_total > 3.0:
                    logger.warning(
                        "%s took %.2fs to stop (became inactive without JobRemoved signal)",
                        service_name,
                        elapsed_total,
                    )
                return
            elif job_task in done:
                try:
                    result = job_task.result()
                    if result is not None and result != "done":
                        logger.warning(
                            "%s Stop job finished with result: %s",
                            service_name,
                            result,
                        )
                except Exception:
                    logger.exception(
                        "%s: error retrieving Stop job result", service_name
                    )
            else:
                # Timeout — neither task completed within the allowed window.
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

            # Phase 2: Wait for processes to actually exit by polling state.
            # Uses _get_unit_property which calls _send() → reconnect-on-error,
            # so a mid-poll connection drop is handled transparently.
            elapsed = time.monotonic() - start_time
            timeout_remaining = max(5.0, timeout - elapsed)
            poll_deadline = time.monotonic() + timeout_remaining
            check_interval = 0.1  # Check every 100ms

            while time.monotonic() < poll_deadline:
                try:
                    active_state = await self._get_unit_property(
                        unit_path,
                        "org.freedesktop.systemd1.Unit",
                        "ActiveState",
                    )

                    # For service units, also check MainPID to ensure process exited
                    main_pid = 0
                    if is_service_unit:
                        main_pid = await self._get_unit_property(
                            unit_path, "org.freedesktop.systemd1.Service", "MainPID"
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
                final_state = await self._get_unit_property(
                    unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
                )
                if is_service_unit:
                    final_main_pid = await self._get_unit_property(
                        unit_path, "org.freedesktop.systemd1.Service", "MainPID"
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

    async def get_wants_tree(self, service_name: str | bytes) -> set[str]:
        """Walk the Wants dependency tree recursively.

        Returns set of all unit names that are (transitively) wanted by the
        given unit.  Only follows the ``Wants`` property — ``Requires``
        failures are already propagated by systemd itself, so ``Wants`` is
        where silent failures hide.
        """
        service_name = self._normalize_unit_name(service_name)
        visited: set[str] = set()
        await self._walk_wants(service_name, visited)
        return visited

    async def _walk_wants(self, unit_name: str, visited: set[str]) -> None:
        if unit_name in visited:
            return
        visited.add(unit_name)
        path = await self._load_unit_path(unit_name)
        wants = await self._get_unit_property(
            path, "org.freedesktop.systemd1.Unit", "Wants"
        )
        for dep in wants:
            await self._walk_wants(dep, visited)

    async def get_failed_units(
        self, unit_names: set[str]
    ) -> dict[str, tuple[str, int]]:
        """Check a set of units for failed or crash-looping state.

        Returns:
            ``{unit_name: (active_state, inactive_exit_timestamp_monotonic)}``
            for every unit whose ``ActiveState`` is ``"failed"`` or whose
            ``SubState`` indicates crash-looping.
        """
        failed: dict[str, tuple[str, int]] = {}
        for name in unit_names:
            path = await self._load_unit_path(name)
            active = await self._get_unit_property(
                path, "org.freedesktop.systemd1.Unit", "ActiveState"
            )
            sub = await self._get_unit_property(
                path, "org.freedesktop.systemd1.Unit", "SubState"
            )
            if active == "failed" or sub in ("auto-restart", "auto-restart-queued"):
                ts = await self._get_unit_property(
                    path,
                    "org.freedesktop.systemd1.Unit",
                    "InactiveExitTimestampMonotonic",
                )
                failed[name] = (active, ts)
        return failed

    async def get_inactive_exit_timestamp(self, service_name: str | bytes) -> int:
        """
        Get InactiveExitTimestampMonotonic for a systemd service via D-Bus.

        Returns:
            Timestamp in microseconds
        """
        service_name = self._normalize_unit_name(service_name)
        unit_path = await self._load_unit_path(service_name)
        return await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Unit", "InactiveExitTimestampMonotonic"
        )

    async def get_service_state(self, service_name: str | bytes) -> tuple[bytes, int]:
        """
        Get ActiveState and MainPID for a systemd service via D-Bus.

        Returns:
            Tuple of (active_state as bytes, main_pid as int)
        """
        service_name = self._normalize_unit_name(service_name)
        unit_path = await self._load_unit_path(service_name)
        active_state = await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
        )
        main_pid = await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Service", "MainPID"
        )
        return active_state.encode(), main_pid

    async def get_unit_active_state(self, service_name: str | bytes) -> str:
        """
        Get ActiveState for a systemd service via D-Bus.

        Returns:
            Active state as string (e.g., "active", "inactive", "activating")
        """
        service_name = self._normalize_unit_name(service_name)
        unit_path = await self._load_unit_path(service_name)
        return await self._get_unit_property(
            unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
        )

    async def get_unit_file_state(self, service_name: str | bytes) -> str:
        """
        Get UnitFileState for a systemd unit via D-Bus.

        Uses the Manager.GetUnitFileState method rather than loading the unit and
        reading its property, because LoadUnit creates stub units for non-existent
        services (returning an empty string) instead of reporting "not-found".

        Returns:
            Unit file state as string (e.g., "enabled", "disabled", "static", "masked", "not-found")
        """
        service_name = self._normalize_unit_name(service_name)
        try:
            msg = new_method_call(
                _SYSTEMD_MANAGER, "GetUnitFileState", "s", (service_name,)
            )
            reply = await self._send(msg)
            return unwrap_msg(reply)[0]
        except DBusErrorResponse as e:
            if e.name == "org.freedesktop.DBus.Error.FileNotFound":
                return "not-found"
            raise

    async def set_unit_file_state(
        self, service_name: str | bytes, enabled: bool
    ) -> None:
        """
        Enable or disable a systemd unit file via D-Bus.
        """
        service_name = self._normalize_unit_name(service_name)

        if enabled:
            msg = new_method_call(
                _SYSTEMD_MANAGER,
                "EnableUnitFiles",
                "asbb",
                ([service_name], False, True),
            )
        else:
            msg = new_method_call(
                _SYSTEMD_MANAGER, "DisableUnitFiles", "asb", ([service_name], False)
            )
        await self._send(msg)

        # Reload the systemd manager configuration so the unit file state change
        # is reflected in runtime state. EnableUnitFiles/DisableUnitFiles only
        # modify symlinks on disk without updating systemd's in-memory state,
        # whereas `systemctl enable/disable` did this implicitly.
        reload_msg = new_method_call(_SYSTEMD_MANAGER, "Reload", "", ())
        await self._send(reload_msg)

    async def call_unit_action(self, service_name: str | bytes, action: str) -> str:
        """
        Call a unit action (Start, Stop, Restart, Reload) and return the job path.

        Returns:
            Job object path
        """
        service_name = self._normalize_unit_name(service_name)
        unit_path = await self._load_unit_path(service_name)

        unit = DBusAddress(
            unit_path,
            bus_name="org.freedesktop.systemd1",
            interface="org.freedesktop.systemd1.Unit",
        )

        msg = new_method_call(unit, action, "s", ("replace",))
        reply = await self._send(msg)
        return unwrap_msg(reply)[0]

    async def call_unit_action_and_wait(
        self, service_name: str | bytes, action: str, timeout: float | None = None
    ) -> None:
        """
        Call a unit action and wait for job completion via D-Bus signals.

        The JobRemoved signal subscription is established once per connection
        in _ensure_router(). This method sets up a local filter to match the
        specific job, avoiding race conditions where the job completes before
        we start listening.

        For Stop actions, delegates to _stop_unit_and_wait_for_exit() which waits
        for processes to actually exit by polling the service state.
        """
        service_name = self._normalize_unit_name(service_name)
        timeout_is_explicit = timeout is not None

        start_time = time.monotonic()

        router = await self._ensure_router()

        unit_path = await self._load_unit_path(service_name)

        if not timeout_is_explicit:
            timeout = await self._get_unit_timeout(unit_path, service_name, action)

        if action == "Stop":
            active_state = await self._get_unit_property(
                unit_path, "org.freedesktop.systemd1.Unit", "ActiveState"
            )
            if active_state in ("inactive", "failed"):
                return
            await self._stop_unit_and_wait_for_exit(
                unit_path,
                service_name,
                timeout,
                start_time,
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
                try:
                    reply = await router.send_and_get_reply(msg)
                except Exception as e:
                    if not isinstance(e, DBusErrorResponse):
                        await self._invalidate()
                    raise
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
            await self._verify_service_running(unit_path, service_name, action)

    async def systemd_unit(self, unit: str | bytes, verb: str) -> None:
        """Perform a systemd unit action via D-Bus."""
        action = _VERB_TO_ACTION.get(verb)
        if action is None:
            raise ValueError(f"Unsupported systemd verb: {verb}")

        await self.call_unit_action_and_wait(self._normalize_unit_name(unit), action)


system_dbus = CachedSystemDBusRouter()
