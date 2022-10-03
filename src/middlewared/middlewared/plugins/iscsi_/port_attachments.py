from middlewared.common.ports import ServicePortDelegate


class ISCSIGlobalServicePortDelegate(ServicePortDelegate):

    name = 'iSCSI'
    namespace = 'iscsi.global'
    port_fields = ['listen_port']
    title = 'iSCSI Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', ISCSIGlobalServicePortDelegate(middleware))
