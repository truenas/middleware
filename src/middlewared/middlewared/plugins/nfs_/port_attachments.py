from middlewared.common.ports import ServicePortDelegate


class NFSServicePortDelegate(ServicePortDelegate):

    bind_address_field = 'bindip'
    name = 'nfs'
    namespace = 'nfs'
    port_fields = ['mountd_port', 'rpcstatd_port', 'rpclockd_port']
    title = 'NFS Service'

    def bind_address(self, config):
        if config[self.bind_address_field] and '0.0.0.0' not in config[self.bind_address_field]:
            return config[self.bind_address_field]
        else:
            return ['0.0.0.0']

    def get_bind_ip_port_tuple(self, config, port_field):
        pass

    async def get_ports_internal(self):
        await self.basic_checks()
        config = await self.config()
        ports = [('0.0.0.0', 2049)]
        bind_addresses = self.bind_address(config)
        for k in filter(lambda k: config.get(k), self.port_fields):
            for bindip in bind_addresses:
                ports.append((bindip, config[k]))

        return ports


async def setup(middleware):
    await middleware.call('port.register_attachment_delegate', NFSServicePortDelegate(middleware))
