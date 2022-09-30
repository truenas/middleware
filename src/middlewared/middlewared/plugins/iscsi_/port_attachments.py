from middlewared.common.ports import ServicePortDelegate


class ISCSIGlobalServicePortDelegate(ServicePortDelegate):

    port_fields = ['listen_port']
    service = 'iscsi.global'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ISCSIGlobalServicePortDelegate(middleware))
