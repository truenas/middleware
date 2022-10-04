import copy

from middlewared.service import Service, ValidationErrors


class PortService(Service):

    DELEGATES = {}
    SYSTEM_USED_PORTS = [
        {'title': 'System', 'ports': [6000], 'namespace': 'system'},
    ]

    class Config:
        private = True

    async def register_attachment_delegate(self, delegate):
        self.DELEGATES[delegate.namespace] = delegate

    async def get_used_ports(self):
        ports = []
        for delegate in self.DELEGATES:
            ports.extend(await delegate.get_ports())
        return ports

    async def get_in_use(self):
        # TODO: Remove either this or the above one probably
        ports = copy.deepcopy(self.SYSTEM_USED_PORTS)
        for delegate in self.DELEGATES.values():
            used_ports = await delegate.get_ports()
            if used_ports:
                ports.append({
                    'namespace': delegate.namespace,
                    'title': delegate.title,
                    'ports': used_ports,
                })

        return ports

    async def validate_port(self, schema, value, whitelist_namespace=None):
        verrors = ValidationErrors()
        for port_attachment in await self.middleware.call('port.get_in_use'):
            if value in port_attachment['ports'] and port_attachment['namespace'] != whitelist_namespace:
                verrors.add(schema, f'The port is being used by {port_attachment["type"]!r}')

        return verrors
