from middlewared.common.ports import ServicePortDelegate


class RsyncdServicePortDelegate(ServicePortDelegate):

    port_fields = ['port']
    service = 'rsyncd'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', RsyncdServicePortDelegate(middleware))
