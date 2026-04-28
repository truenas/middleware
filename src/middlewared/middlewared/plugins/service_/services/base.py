import logging

from middlewared.utils.journal import (
    format_journal_record,
    monotonic_to_realtime_since,
    query_journal,
)

from .base_interface import IdentifiableServiceInterface, ServiceInterface
from .base_state import ServiceState
from .dbus_router import system_dbus

logger = logging.getLogger(__name__)


class SimpleService(ServiceInterface, IdentifiableServiceInterface):
    systemd_unit: str
    systemd_async_start = False

    async def systemd_extra_units(self):
        return []

    async def get_state(self):
        unit_name = self._get_systemd_unit_name()
        state, main_pid = await system_dbus.get_service_state(unit_name)
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
        return await system_dbus.get_unit_active_state(unit_name)

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

    async def get_failed_sub_units(self):
        unit_name = self._get_systemd_unit_name()
        try:
            wants_tree = await system_dbus.get_wants_tree(unit_name)
            return await system_dbus.get_failed_units(wants_tree)
        except Exception:
            logger.debug("Failed to walk Wants tree for %s", unit_name, exc_info=True)
            return {}

    async def failure_logs(self, failed_units=None):
        # Walk the Wants dependency tree and find failed/crash-looping units.
        # This catches sub-unit failures (e.g. nut-driver@ups crash-looping
        # under nut-monitor) that the main unit's logs wouldn't show.
        if failed_units is None:
            failed_units = await self.get_failed_sub_units()

        if failed_units:
            units_info = list(failed_units.items())
        else:
            # Fall back to querying the main unit (original behavior)
            unit_name = self._get_systemd_unit_name()
            monotonic_ts = await system_dbus.get_inactive_exit_timestamp(unit_name)
            units_info = [(unit_name, ("unknown", monotonic_ts))]

        return await self.middleware.run_in_thread(
            self._collect_failure_logs, units_info
        )

    def _get_systemd_unit_name(self):
        return f"{self.systemd_unit}.service"

    async def _unit_action(self, action, wait=True):
        unit_name = self._get_systemd_unit_name()
        if wait:
            await self._call_unit_action_and_wait(unit_name, action)
        else:
            await system_dbus.call_unit_action(unit_name, action)

    async def _call_unit_action_and_wait(self, service_name, action, timeout=None):
        await system_dbus.call_unit_action_and_wait(service_name, action, timeout)

    async def _systemd_unit(self, unit, verb):
        await system_dbus.systemd_unit(unit, verb)

    @staticmethod
    def _collect_failure_logs(units_info):
        """Collect journalctl logs for one or more failed units.

        Args:
            units_info: list of ``(unit_name, (active_state, monotonic_timestamp))``
        """
        # Match logic from systemd's add_matches_for_unit
        # (https://github.com/systemd/systemd/blob/main/src/shared/logs-show.c)
        # Using + for OR (disjunction) between match groups
        all_sections: list[str] = []
        for unit_name, (_state, monotonic_ts) in units_info:
            since = monotonic_to_realtime_since(monotonic_ts)
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
            if records:
                all_sections.append(
                    "\n".join(format_journal_record(r) for r in records)
                )
        return "\n".join(all_sections)


class SwitchableSimpleService(SimpleService):
    """SimpleService variant that supports runtime selection of the systemd
    unit and etc groups.  Subclasses override `select_systemd_unit_name()`
    and/or `select_etc()` to switch behaviour based on operating mode (e.g.
    kernel-stack vs userspace-stack).  Returning `None` from
    `select_systemd_unit_name()` means no systemd unit is involved; override
    `get_state_no_unit()` to provide an alternative running-state check."""

    async def select_systemd_unit_name(self) -> str | None:
        return self.systemd_unit

    async def get_state_no_unit(self) -> "ServiceState":
        return ServiceState(False, [])

    async def get_state(self):
        unit = await self.select_systemd_unit_name()
        if unit is None:
            return await self.get_state_no_unit()
        unit_name = f"{unit}.service"
        state, main_pid = await system_dbus.get_service_state(unit_name)
        if (
            state == b"active"
            or (self.systemd_async_start and state == b"activating")
            or state == b"reloading"
        ):
            return ServiceState(True, list(filter(None, [main_pid])))
        return ServiceState(False, [])

    async def get_unit_state(self):
        unit = await self.select_systemd_unit_name()
        if unit is None:
            return None
        return await system_dbus.get_unit_active_state(f"{unit}.service")

    async def _unit_action(self, action, wait=True):
        unit = await self.select_systemd_unit_name()
        if unit is None:
            return
        unit_name = f"{unit}.service"
        if wait:
            await self._call_unit_action_and_wait(unit_name, action)
        else:
            await system_dbus.call_unit_action(unit_name, action)

    async def get_failed_sub_units(self):
        unit = await self.select_systemd_unit_name()
        if unit is None:
            return {}
        unit_name = f"{unit}.service"
        try:
            wants_tree = await system_dbus.get_wants_tree(unit_name)
            return await system_dbus.get_failed_units(wants_tree)
        except Exception:
            logger.debug("Failed to walk Wants tree for %s", unit_name, exc_info=True)
            return {}

    async def failure_logs(self, failed_units=None):
        unit = await self.select_systemd_unit_name()
        if failed_units is None:
            failed_units = await self.get_failed_sub_units()
        if failed_units:
            units_info = list(failed_units.items())
        elif unit is not None:
            unit_name = f"{unit}.service"
            monotonic_ts = await system_dbus.get_inactive_exit_timestamp(unit_name)
            units_info = [(unit_name, ("unknown", monotonic_ts))]
        else:
            return ""
        return await self.middleware.run_in_thread(
            self._collect_failure_logs, units_info
        )
