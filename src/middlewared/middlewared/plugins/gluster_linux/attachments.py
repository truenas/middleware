from middlewared.common.ports import ServicePortDelegate


class GlusterServicePortDelegate(ServicePortDelegate):

    name = 'gluster'
    namespace = 'gluster.fuse'
    title = 'Gluster Service'

    async def get_ports_internal(self):
        return [24007, 24008]


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', GlusterServicePortDelegate(middleware))
