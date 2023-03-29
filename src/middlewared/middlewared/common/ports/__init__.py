from collections.abc import Iterable

from middlewared.plugins.ports.utils import WILDCARD_IPS


class PortDelegate:

    name = NotImplemented
    namespace = NotImplemented
    title = NotImplemented

    def __init__(self, middleware):
        self.middleware = middleware
        self.logger = middleware.logger
        for k in ('name', 'namespace', 'title'):
            if getattr(self, k) is NotImplemented:
                raise ValueError(f'{k!r} must be specified for port delegate')

    async def get_ports(self):
        raise NotImplementedError()


class ServicePortDelegate(PortDelegate):
    bind_address_field = NotImplemented
    port_fields = NotImplemented

    async def basic_checks(self):
        if self.port_fields is NotImplemented:
            raise ValueError('Port fields must be set for Service port delegate')
        elif not isinstance(self.port_fields, Iterable):
            raise ValueError('Port fields must be an iterable')

    def bind_address(self, config):
        default = '0.0.0.0'
        return default if self.bind_address_field is NotImplemented else (
            config.get(self.bind_address_field) or default
        )

    def get_bind_ip_port_tuple(self, config, port_field):
        return self.bind_address(config), config[port_field]

    async def config(self):
        return await self.middleware.call(f'{self.namespace}.config')

    async def get_ports_bound_on_wildcards(self):
        return []

    async def get_ports_internal(self):
        if override_ports := await self.get_ports_bound_on_wildcards():
            return [(wildcard, port) for wildcard in WILDCARD_IPS for port in override_ports]

        await self.basic_checks()
        config = await self.config()
        return [self.get_bind_ip_port_tuple(config, k) for k in filter(lambda k: config.get(k), self.port_fields)]

    async def get_ports(self):
        ports = await self.get_ports_internal()
        return [{'description': None, 'ports': ports}] if ports else []
