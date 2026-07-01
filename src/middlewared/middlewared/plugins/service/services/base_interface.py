from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.utils.service.call_mixin import CallMixin

if TYPE_CHECKING:
    from middlewared.main import Middleware

    from .base_state import ServiceState


class ServiceInterface(CallMixin):
    name: str

    etc: list[str] = []
    restartable = False  # Implements `restart` method instead of `stop` + `start`
    reloadable = False  # Implements `reload` method
    deprecated = False  # Alert if service is running
    may_run_on_standby = True  # should be allowed to run on HA standby

    def __init__(self, middleware: Middleware) -> None:
        self.middleware = middleware

    async def get_state(self) -> ServiceState:
        raise NotImplementedError

    async def get_unit_state(self) -> str | None:
        raise NotImplementedError

    async def become_active(self) -> None:
        raise NotImplementedError

    async def become_standby(self) -> None:
        raise NotImplementedError

    async def check_configuration(self) -> None:
        pass

    async def start(self) -> None:
        raise NotImplementedError

    async def before_start(self) -> None:
        pass

    async def after_start(self) -> None:
        pass

    async def stop(self) -> None:
        raise NotImplementedError

    async def before_stop(self) -> None:
        pass

    async def after_stop(self) -> None:
        pass

    async def restart(self) -> None:
        raise NotImplementedError

    async def before_restart(self) -> None:
        pass

    async def after_restart(self) -> None:
        pass

    async def reload(self) -> None:
        raise NotImplementedError

    async def before_reload(self) -> None:
        pass

    async def after_reload(self) -> None:
        pass

    async def select_etc(self) -> list[str]:
        return self.etc

    async def systemd_extra_units(self) -> list[str]:
        return []

    async def get_failed_sub_units(self) -> dict[str, tuple[str, int]]:
        """Return dict of failed/crash-looping units in the dependency tree.

        Returns:
            ``{unit_name: (active_state, inactive_exit_timestamp_monotonic)}``
            for every unit whose ``ActiveState`` is ``"failed"`` or whose
            ``SubState`` indicates crash-looping. Empty dict means healthy.
        """
        return {}

    async def failure_logs(self, failed_units:  dict[str, tuple[str, int]] | None = None) -> str:
        raise NotImplementedError


class IdentifiableServiceInterface:
    async def identify(self, procname: str) -> bool:
        raise NotImplementedError
