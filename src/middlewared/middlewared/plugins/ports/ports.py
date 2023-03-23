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
        port_attachment = port_mapping[port]
        if not port_attachment or (
            bindip not in port_attachment and '0.0.0.0' not in port_attachment and bindip != '0.0.0.0'
        ):
            return verrors

        ip_errors = []
        for index, port_detail in enumerate(port_attachment.items()):
            ip, port_entry = port_detail
            if bindip == '0.0.0.0' or ip == '0.0.0.0' or (bindip != '0.0.0.0' and ip == bindip):
                entry = next(
                    detail for detail in port_entry['port_details'] if (ip, port) in detail['ports']
                )
                description = entry['description']
                ip_errors.append(
                    f'{index + 1}) "{ip}:{port}" used by {port_entry["title"]}'
                    f'{f" ({description})" if description else ""}'
                )

        err = '\n'.join(ip_errors)
        verrors.add(
            schema,
            f'The port is being used by following services:\n{err}'
        )

        if raise_error:
            verrors.check()

        return verrors

    async def ports_mapping(self, whitelist_namespace=None):
        ports = defaultdict(dict)
        for attachment in filter(lambda entry: entry['namespace'] != whitelist_namespace, await self.get_in_use()):
            for bindip, port in attachment['ports']:
                ports[port][bindip] = attachment

        return ports
