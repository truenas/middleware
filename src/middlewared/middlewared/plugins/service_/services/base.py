from middlewared.utils.journal import (
    format_journal_record,
    monotonic_to_realtime_since,
    query_journal,
)

from .base_interface import ServiceInterface, IdentifiableServiceInterface
from .base_state import ServiceState
from .dbus_router import system_dbus


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

    async def failure_logs(self):
        unit_name = self._get_systemd_unit_name()
        monotonic_timestamp = await system_dbus.get_inactive_exit_timestamp(unit_name)
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
            await system_dbus.call_unit_action(unit_name, action)

    async def _call_unit_action_and_wait(self, service_name, action, timeout=None):
        await system_dbus.call_unit_action_and_wait(service_name, action, timeout)

    async def _systemd_unit(self, unit, verb):
        await system_dbus.systemd_unit(unit, verb)

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
