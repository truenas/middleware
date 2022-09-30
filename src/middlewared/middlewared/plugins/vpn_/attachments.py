from middlewared.common.ports import ServicePortDelegate


class OpenVPNServerServicePortDelegate(ServicePortDelegate):

    port_fields = ['port']
    service = 'openvpn.server'


class OpenVPNClientServicePortDelegate(ServicePortDelegate):

    port_fields = ['port']
    service = 'openvpn.client'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', OpenVPNServerServicePortDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', OpenVPNClientServicePortDelegate(middleware))
