from __future__ import annotations

from typing import TYPE_CHECKING

from middlewared.common.ports import PortDelegate, PortDetail

if TYPE_CHECKING:
    from middlewared.main import Middleware


class AppPortDelegate(PortDelegate):

    name = 'applications'
    namespace = 'app'
    title = 'Applications'

    async def get_ports(self) -> list[PortDetail]:
        ports: list[PortDetail] = []
        for app in filter(
            lambda a: a.active_workloads.used_ports,
            await self.call2(self.s.app.query)
        ):
            app_ports: list[tuple[str, int]] = []
            for port_entry in app.active_workloads.used_ports:
                for host_port in port_entry.host_ports:
                    app_ports.append((host_port.host_ip, host_port.host_port))

            ports.append({
                'description': f'{app.id!r} application',
                'ports': app_ports,
            })

        return ports


async def setup(middleware: Middleware) -> None:
    await middleware.call('port.register_attachment_delegate', AppPortDelegate(middleware))
