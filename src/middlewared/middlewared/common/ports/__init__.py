from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Required, TypedDict

from middlewared.utils.service.call_mixin import CallMixin

if TYPE_CHECKING:
    from logging import Logger

    from middlewared.main import Middleware


WILDCARD_IPS: list[str] = ["0.0.0.0", "::"]


class PortEntry(TypedDict, total=False):
    port: Required[int]
    bindip: str


class PortDetail(TypedDict):
    description: str | None
    ports: list[tuple[str, int]]


class PortInUse(TypedDict):
    namespace: str
    title: str
    ports: list[list[str | int]]
    port_details: list[PortDetail]


class PortDelegate(CallMixin):

    name: str
    namespace: str
    title: str

    def __init__(self, middleware: Middleware) -> None:
        self.middleware: Middleware = middleware
        self.logger: Logger = middleware.logger
        for k in ("name", "namespace", "title"):
            if not hasattr(self, k):
                raise ValueError(f"{k!r} must be specified for port delegate")

    async def get_ports(self) -> list[PortDetail]:
        raise NotImplementedError()


class ServicePortDelegate(PortDelegate):
    bind_address_field: str
    port_fields: Iterable[str]

    async def basic_checks(self) -> None:
        if not hasattr(self, "port_fields"):
            raise ValueError("Port fields must be set for Service port delegate")
        elif not isinstance(self.port_fields, Iterable):
            raise ValueError("Port fields must be an iterable")

    def bind_address(self, config: dict[str, Any]) -> str:
        default = "0.0.0.0"
        if hasattr(self, "bind_address_field"):
            return config.get(self.bind_address_field) or default
        return default

    def get_bind_ip_port_tuple(self, config: dict[str, Any], port_field: str) -> tuple[str, int]:
        return self.bind_address(config), config[port_field]

    async def config(self) -> dict[str, Any]:
        return await self.middleware.call(f"{self.namespace}.config")  # type: ignore[no-any-return]

    async def get_ports_bound_on_wildcards(self) -> list[int]:
        return []

    async def get_ports_internal(self) -> list[tuple[str, int]]:
        if override_ports := await self.get_ports_bound_on_wildcards():
            return [(wildcard, port) for wildcard in WILDCARD_IPS for port in override_ports]

        await self.basic_checks()
        config = await self.config()
        return [self.get_bind_ip_port_tuple(config, k) for k in filter(lambda k: config.get(k), self.port_fields)]

    async def get_ports(self) -> list[PortDetail]:
        ports = await self.get_ports_internal()
        return [{"description": None, "ports": ports}] if ports else []
