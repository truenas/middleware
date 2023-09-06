from middlewared.common.ports import ServicePortDelegate

from .netdata.utils import NETDATA_PORT


class ReportingServicePortDelegate(ServicePortDelegate):

    name = 'reporting'
    namespace = 'reporting'
    title = 'Reporting Service'

    async def get_ports_bound_on_wildcards(self):
        return [NETDATA_PORT]


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ReportingServicePortDelegate(middleware))
