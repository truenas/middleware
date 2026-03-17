from __future__ import annotations

from collections import defaultdict
from typing import Any

from middlewared.common.ports import PortDelegate
from middlewared.service import Service, ValidationErrors

from . import ports as _ports

__all__ = ('PortService',)


class PortService(Service):

    class Config:
        private = True

    async def register_attachment_delegate(self, delegate: PortDelegate) -> None:
        _ports.register_attachment_delegate(delegate)

    async def get_in_use(self) -> list[dict[str, Any]]:
        return await _ports.get_in_use()

    async def get_all_used_ports(self) -> list[int]:
        return await _ports.get_all_used_ports()

    async def get_unused_ports(self, lower_port_limit: int = 1025) -> list[int]:
        return await _ports.get_unused_ports(lower_port_limit)

    async def validate_port(
        self,
        schema: str,
        port: int,
        bindip: str = '0.0.0.0',
        whitelist_namespace: str | None = None,
        raise_error: bool = False,
    ) -> ValidationErrors | None:
        return await _ports.validate_port(schema, port, bindip, whitelist_namespace, raise_error)

    async def ports_mapping(self, whitelist_namespace: str | None = None) -> defaultdict[int, dict[str, Any]]:
        return await _ports.ports_mapping(whitelist_namespace)
