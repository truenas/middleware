from middlewared.common.ports import ServicePortDelegate


class OpenVPNServerServicePortDelegate(ServicePortDelegate):

    name = 'Openvpn Server'
    port_fields = ['port']
    namespace = 'openvpn.server'
    title = 'Openvpn Server Service'


class OpenVPNClientServicePortDelegate(ServicePortDelegate):

    name = 'Openvpn Client'
    port_fields = ['port']
    namespace = 'openvpn.client'
    title = 'Openvpn Client Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', OpenVPNServerServicePortDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', OpenVPNClientServicePortDelegate(middleware))
