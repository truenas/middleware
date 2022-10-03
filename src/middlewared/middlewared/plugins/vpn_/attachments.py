from middlewared.common.ports import ServicePortDelegate


class OpenVPNServerServicePortDelegate(ServicePortDelegate):

    name = 'Openvpn Server'
    namespace = 'openvpn.server'
    port_fields = ['port']
    title = 'Openvpn Server Service'


class OpenVPNClientServicePortDelegate(ServicePortDelegate):

    name = 'Openvpn Client'
    namespace = 'openvpn.client'
    port_fields = ['port']
    title = 'Openvpn Client Service'


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', OpenVPNServerServicePortDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', OpenVPNClientServicePortDelegate(middleware))
