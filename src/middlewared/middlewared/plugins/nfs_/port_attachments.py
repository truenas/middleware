from __future__ import annotations

from typing import TYPE_CHECKING, Any

from middlewared.common.ports import ServicePortDelegate

if TYPE_CHECKING:
    from middlewared.main import Middleware


class NFSServicePortDelegate(ServicePortDelegate):

    bind_address_field = 'bindip'
    name = 'nfs'
    namespace = 'nfs'
    port_fields = ['mountd_port', 'rpcstatd_port', 'rpclockd_port']
    title = 'NFS Service'

    def bind_address(self, config: dict[str, Any]) -> list[str]:  # type: ignore[override]
        if config[self.bind_address_field] and '0.0.0.0' not in config[self.bind_address_field]:
            return config[self.bind_address_field]  # type: ignore[no-any-return]
        else:
            return ['0.0.0.0']

    async def get_ports_internal(self) -> list[tuple[str, int]]:
        await self.basic_checks()
        config = await self.config()
        ports = [('0.0.0.0', 2049)]
        bind_addresses = self.bind_address(config)
        for k in filter(lambda k: config.get(k), self.port_fields):
            for bindip in bind_addresses:
                ports.append((bindip, config[k]))

        return ports


async def setup(middleware: Middleware) -> None:
    await middleware.call('port.register_attachment_delegate', NFSServicePortDelegate(middleware))
