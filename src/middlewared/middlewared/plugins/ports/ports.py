from middlewared.service import Service, ValidationErrors


class PortService(Service):

    DELEGATES = {}
    SYSTEM_USED_PORTS = [
        {'title': 'System', 'ports': [67, 123, 3702, 5353, 6000], 'namespace': 'system'},
    ]

    class Config:
        private = True

    async def register_attachment_delegate(self, delegate):
        self.DELEGATES[delegate.namespace] = delegate

    async def get_in_use(self):
        ports = []
        for delegate in self.DELEGATES.values():
            used_ports = await delegate.get_ports()
            if used_ports:
                ports.append({
                    'namespace': delegate.namespace,
                    'title': delegate.title,
                    'ports': used_ports,
                })

        return ports + self.SYSTEM_USED_PORTS

    async def validate_port(self, schema, value, whitelist_namespace=None):
        verrors = ValidationErrors()
        for port_attachment in await self.middleware.call('port.get_in_use'):
            if value in port_attachment['ports'] and port_attachment['namespace'] != whitelist_namespace:
                verrors.add(schema, f'The port is being used by {port_attachment["type"]!r}')

        return verrors
