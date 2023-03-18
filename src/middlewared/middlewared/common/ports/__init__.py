from collections.abc import Iterable


class PortDelegate:

    name = NotImplementedError
    namespace = NotImplementedError
    title = NotImplementedError

    def __init__(self, middleware):
        self.middleware = middleware
        self.logger = middleware.logger
        for k in ('name', 'namespace', 'title'):
            if getattr(self, k) is NotImplementedError:
                raise ValueError(f'{k!r} must be specified for port delegate')

    async def get_ports(self):
        raise NotImplementedError


class ServicePortDelegate(PortDelegate):
    bind_address_field = NotImplementedError
    port_fields = NotImplementedError

    async def basic_checks(self):
        if self.port_fields is NotImplementedError:
            raise ValueError('Port fields must be set for Service port delegate')
        elif not isinstance(self.port_fields, Iterable):
            raise ValueError('Port fields must be an iterable')

    def bind_address(self, config):
        default = '0.0.0.0'
        return default if self.bind_address_field is NotImplementedError else (
            config.get(self.bind_address_field) or default
        )

    def get_bind_ip_port_tuple(self, config, port_field):
        return self.bind_address(config), config[port_field]

    async def config(self):
        return await self.middleware.call(f'{self.namespace}.config')

    async def get_ports_internal_override(self):
        return []

    async def get_ports_internal(self):
        if override_ports := await self.get_ports_internal_override():
            return [('0.0.0.0', port) for port in override_ports]

        await self.basic_checks()
        config = await self.config()
        return [self.get_bind_ip_port_tuple(config, k) for k in filter(lambda k: config.get(k), self.port_fields)]

    async def get_ports(self):
        ports = await self.get_ports_internal()
        return [{'description': None, 'ports': ports}] if ports else []
