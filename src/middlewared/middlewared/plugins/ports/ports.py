import itertools

from collections import defaultdict

from middlewared.service import Service, ValidationErrors


SYSTEM_PORTS = [('0.0.0.0', port) for port in [67, 123, 3702, 5353, 6000]]


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

    async def validate_port(self, schema, port, bindip='0.0.0.0', whitelist_namespace=None, raise_error=False):
        verrors = ValidationErrors()
        port_mapping = await self.ports_mapping(whitelist_namespace)
        if port not in port_mapping.get(bindip, {}) and port not in port_mapping['0.0.0.0']:
            return verrors

        problematic_bindip = bindip if port_mapping[bindip].get(port) else '0.0.0.0'
        port_attachment = port_mapping[problematic_bindip][port]
        port_entry = next(
            entry for entry in port_attachment['port_details'] if (problematic_bindip, port) in entry['ports']
        )
        err = 'The port is being used by '
        if port_entry['description']:
            err += f'{port_entry["description"]!r} in {port_attachment["title"]!r}'
        else:
            err += f'{port_attachment["title"]!r}'

        verrors.add(schema, err)
        if raise_error:
            verrors.check()

    async def ports_mapping(self, whitelist_namespace=None):
        ports = defaultdict(dict)
        for attachment in filter(lambda entry: entry['namespace'] != whitelist_namespace, await self.get_in_use()):
            for bindip, port in attachment['ports']:
                ports[bindip][port] = attachment

        return ports
