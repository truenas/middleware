import itertools

from middlewared.service import Service, ValidationErrors


SYSTEM_PORTS = [67, 123, 3702, 5353, 6000]


class PortService(Service):

    DELEGATES = {}
    SYSTEM_USED_PORTS = [
        {
            'title': 'System',
            'ports': SYSTEM_PORTS,
            'port_details': [{'description': None, 'ports': SYSTEM_PORTS}],
            'namespace': 'system',
        },
    ]

    class Config:
        private = True

    async def register_attachment_delegate(self, delegate):
        if delegate.namespace in self.DELEGATES:
            raise ValueError(f'{delegate.namespace!r} delegate is already registered with Port Service')
        self.DELEGATES[delegate.namespace] = delegate

    async def get_in_use(self):
        ports = []
        for delegate in self.DELEGATES.values():
            used_ports = await delegate.get_ports()
            if used_ports:
                ports.append({
                    'namespace': delegate.namespace,
                    'title': delegate.title,
                    'ports': list(itertools.chain(*[entry['ports'] for entry in used_ports])),
                    'port_details': used_ports,
                })

        return ports + self.SYSTEM_USED_PORTS

    async def validate_port(self, schema, value, whitelist_namespace=None):
        verrors = ValidationErrors()
        for port_attachment in await self.middleware.call('port.get_in_use'):
            if value in port_attachment['ports'] and port_attachment['namespace'] != whitelist_namespace:
                verrors.add(schema, f'The port is being used by {port_attachment["type"]!r}')

        return verrors
