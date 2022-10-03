from middlewared.common.ports import ServicePortDelegate


class ReportingServicePortDelegate(ServicePortDelegate):

    name = 'reporting'
    namespace = 'reporting'
    title = 'Reporting Service'

    async def get_ports(self):
        return [2003]


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ReportingServicePortDelegate(middleware))
