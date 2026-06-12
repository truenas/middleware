from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from middlewared.main import Middleware


class ListenDelegate[ListenState]:
    """
    Represents something (e.g. service) that needs to handle a deletion of a static IP address from the system.
    """

    async def get_listen_state(self, ips: list[str]) -> ListenState:
        """
        Returns a state object that will be passed to subsequent functions.
        """
        raise NotImplementedError

    async def set_listen_state(self, state: ListenState) -> None:
        """
        Set to listen on the addresses from the state.
        """
        raise NotImplementedError

    async def listens_on(self, state: ListenState, ip: str) -> bool:
        """
        Checks if we are listening on an IP address.
        """
        raise NotImplementedError

    async def reset_listens(self, state: ListenState) -> None:
        """
        Listen on all IP addresses.
        """
        raise NotImplementedError

    async def repr(self, state: ListenState) -> dict[str, str]:
        """
        Returns machine-readable state description.
        """
        raise NotImplementedError


class ConfigServiceListenDelegate[ListenState](ListenDelegate[ListenState]):
    """
    ConfigService listening on IP address.
    """

    def __init__(self, middleware: Middleware, plugin: str, field: str) -> None:
        self.middleware = middleware
        self.plugin = plugin
        self.field = field

    async def get_listen_state(self, ips: list[str]) -> ListenState:
        config = await self.middleware.call(f"{self.plugin}.config")
        return config[self.field]  # type: ignore[no-any-return]

    async def set_listen_state(self, state: ListenState) -> None:
        await self.middleware.call(f"{self.plugin}.update", {self.field: state})

    async def repr(self, state: ListenState) -> dict[str, str]:
        return {"type": "SERVICE", "service": self.plugin}

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} {self.plugin}>"


class ConfigServiceListenSingleDelegate(ConfigServiceListenDelegate[str]):
    """
    ConfigService listening on a single IP address.
    """

    def __init__(self, *args: Any, empty_value: str = "0.0.0.0"):
        super().__init__(*args)
        self.empty_value = empty_value

    async def listens_on(self, state: str, ip: str) -> bool:
        return state == ip

    async def reset_listens(self, state: str) -> None:
        await self.set_listen_state(self.empty_value)


class ConfigServiceListenMultipleDelegate(ConfigServiceListenDelegate[list[str]]):
    """
    ConfigService listening on multiple IP addresses.
    """

    async def listens_on(self, state: list[str], ip: str) -> bool:
        return ip in state

    async def reset_listens(self, state: list[str]) -> None:
        await self.set_listen_state([])


class SystemServiceListenDelegateMixin[ListenState]:
    @property
    def service(self) -> str:
        return self.middleware.get_service(self.plugin)._config.service  # type: ignore[attr-defined, no-any-return]

    async def repr(self, state: ListenState) -> dict[str, str]:
        return {"type": "SYSTEM_SERVICE", "service": self.service}


class SystemServiceListenSingleDelegate(SystemServiceListenDelegateMixin[str], ConfigServiceListenSingleDelegate):
    pass


class SystemServiceListenMultipleDelegate(SystemServiceListenDelegateMixin[list[str]],
                                          ConfigServiceListenMultipleDelegate):
    pass
