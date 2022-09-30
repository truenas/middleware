from middlewared.common.ports import ServicePortDelegate


class NFSServicePortDelegate(ServicePortDelegate):

    port_fields = ['mountd_port', 'rpcstatd_port', 'rpclockd_port']
    service = 'nfs'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', NFSServicePortDelegate(middleware))
