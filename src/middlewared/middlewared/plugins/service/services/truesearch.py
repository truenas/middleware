from middlewared.plugins.service.services.base import SimpleService
from middlewared.plugins.service.services.base_state import ServiceState
from middlewared.plugins.service.services.dbus_router import system_dbus

INDEXER_UNIT = "truesearch-indexer"


class TruesearchService(SimpleService):
    """
    The service runs two units. truesearchd serves searches, and truesearch-indexer builds and keeps the indexes.
    """
    name = "truesearch"

    etc = ["truesearch"]
    reloadable = True
    may_run_on_standby = False

    systemd_unit = "truesearchd"

    async def systemd_extra_units(self) -> list[str]:
        return [INDEXER_UNIT]

    async def get_state(self) -> ServiceState:
        # The service runs when both units run. `configure` starts a dead indexer again.
        state = await super().get_state()
        if state.running and await system_dbus.get_unit_active_state(INDEXER_UNIT) != "active":
            return ServiceState(False, [])

        return state

    async def start(self) -> None:
        await self._systemd_unit(INDEXER_UNIT, "start")
        await super().start()

    async def stop(self) -> None:
        await super().stop()
        await self._systemd_unit(INDEXER_UNIT, "stop")

    async def restart(self) -> None:
        await self._systemd_unit(INDEXER_UNIT, "restart")
        await super().restart()

    async def reload(self) -> None:
        await self._systemd_unit(INDEXER_UNIT, "reload")
        await super().reload()
