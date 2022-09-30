from collections.abc import Iterable


class PortDelegate:

    name = NotImplementedError
    title = NotImplementedError

    def __init__(self, middleware):
        self.middleware = middleware
        self.logger = middleware.logger

    async def get_ports(self):
        raise NotImplementedError


class ServicePortDelegate(PortDelegate):
    # service object
    port_fields = NotImplementedError
    service = NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.port_fields is NotImplementedError:
            raise ValueError('Port fields must be set for Service port delegate')
        elif not isinstance(self.port_fields, Iterable):
            raise ValueError('Port fields must be an iterable')

    async def get_ports(self):
        config = await self.middleware.call(f'{self.service}.config')
        return [config[k] for k in filter(lambda k: config.get(k), self.port_fields)]
