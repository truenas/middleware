class PortDelegate:

    def __init__(self, middleware):
        self.middleware = middleware
        self.logger = middleware.logger

    async def get_ports(self):
        raise NotImplementedError


class ServicePortDelegate(PortDelegate):
    # service object
    port_fields = NotImplementedError
    service = NotImplementedError

    async def get_ports(self):
        config = await self.middleware.call(f'{self.service}.config')
        return [config[k] for k in self.port_fields]
