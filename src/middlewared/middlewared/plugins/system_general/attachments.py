from middlewared.common.ports import ServicePortDelegate


class SystemGeneralServicePortDelegate(ServicePortDelegate):

    bind_address_field = 'ui_address'
    name = 'webui'
    namespace = 'system.general'
    port_fields = ['ui_port', 'ui_httpsport']
    title = 'WebUI Service'

    def bind_address(self, config):
        addresses = []
        for wildcard_ip, address_field in (
            ('0.0.0.0', 'ui_address'),
            ('::', 'ui_v6address'),
        ):
            if config[address_field] and wildcard_ip not in config[address_field]:
                addresses.extend(config[address_field])
            else:
                addresses.append(wildcard_ip)

        return addresses

    async def get_ports_internal(self):
        await self.basic_checks()
        config = await self.config()
        ports = []
        bind_addresses = self.bind_address(config)
        for k in filter(lambda k: config.get(k), self.port_fields):
            for bindip in bind_addresses:
                ports.append((bindip, config[k]))

        return ports


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', SystemGeneralServicePortDelegate(middleware))
