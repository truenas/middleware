from __future__ import annotations

import typing

from middlewared.common.ports import ServicePortDelegate

from .netdata.utils import NETDATA_PORT

if typing.TYPE_CHECKING:
    from middlewared.main import Middleware


class ReportingServicePortDelegate(ServicePortDelegate):

    name = 'reporting'
    namespace = 'reporting'
    title = 'Reporting Service'

    async def get_ports_bound_on_wildcards(self) -> list[int]:
        return [NETDATA_PORT]


async def setup(middleware: Middleware) -> None:
    await middleware.call('port.register_attachment_delegate', ReportingServicePortDelegate(middleware))
