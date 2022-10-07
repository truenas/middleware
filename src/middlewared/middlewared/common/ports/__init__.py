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
    port_fields = NotImplementedError

    async def basic_checks(self):
        if self.port_fields is NotImplementedError:
            raise ValueError('Port fields must be set for Service port delegate')
        elif not isinstance(self.port_fields, Iterable):
            raise ValueError('Port fields must be an iterable')

    async def get_ports_internal(self):
        await self.basic_checks()
        config = await self.middleware.call(f'{self.namespace}.config')
        return [config[k] for k in filter(lambda k: config.get(k), self.port_fields)]

    async def get_ports(self):
        ports = await self.get_ports_internal()
        return [{'description': None, 'ports': ports}] if ports else []
