class PortDelegate:

    def __init__(self, middleware):
        self.middleware = middleware
        self.logger = middleware.logger

    async def get_ports(self):
        raise NotImplementedError


class ServicePortDelegate(PortDelegate):
    # service object
    service_class = NotImplementedError
    port_fields = NotImplementedError

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port_field = self.service_class.path_field
        self.datastore_model = self.service_class._config.datastore
        self.datastore_prefix = self.service_class._config.datastore_prefix
        self.namespace = self.service_class._config.namespace

    async def get_ports(self):
        config = await self.middleware.call(f'{self.namespace}.config')
        return [config[k] for k in self.port_fields]
