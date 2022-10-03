from middlewared.common.ports import ServicePortDelegate


class RsyncdServicePortDelegate(ServicePortDelegate):

    name = 'rsyncd'
    port_fields = ['port']
    namespace = 'rsyncd'
    title = 'Rsyncd Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', RsyncdServicePortDelegate(middleware))
