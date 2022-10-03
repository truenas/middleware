from middlewared.common.ports import ServicePortDelegate


class RsyncdServicePortDelegate(ServicePortDelegate):

    name = 'rsyncd'
    namespace = 'rsyncd'
    port_fields = ['port']
    title = 'Rsyncd Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', RsyncdServicePortDelegate(middleware))
