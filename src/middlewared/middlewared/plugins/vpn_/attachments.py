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

    async def get_ports_internal(self):
        await self.basic_checks()
        config = await self.middleware.call(f'{self.namespace}.config')
        if config['nobind']:
            return []
        else:
            return [config[k] for k in filter(lambda k: config.get(k), self.port_fields)]


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', OpenVPNServerServicePortDelegate(middleware))
    await middleware.call('port.register_attachment_delegate', OpenVPNClientServicePortDelegate(middleware))
