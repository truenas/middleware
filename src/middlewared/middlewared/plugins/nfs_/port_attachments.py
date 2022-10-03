from middlewared.common.ports import ServicePortDelegate


class NFSServicePortDelegate(ServicePortDelegate):

    name = 'nfs'
    namespace = 'nfs'
    port_fields = ['mountd_port', 'rpcstatd_port', 'rpclockd_port']
    title = 'NFS Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', NFSServicePortDelegate(middleware))
