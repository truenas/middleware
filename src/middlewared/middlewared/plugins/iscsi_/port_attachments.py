from middlewared.common.ports import ServicePortDelegate


class ISCSIGlobalServicePortDelegate(ServicePortDelegate):

    name = 'iSCSI'
    port_fields = ['listen_port']
    service = 'iscsi.global'
    title = 'iSCSI Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ISCSIGlobalServicePortDelegate(middleware))
