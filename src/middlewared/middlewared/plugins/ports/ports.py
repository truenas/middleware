import ipaddress
import itertools

from collections import defaultdict

from middlewared.service import Service, ValidationErrors

from .utils import WILDCARD_IPS


SYSTEM_PORTS = [(wildcard, port) for wildcard in WILDCARD_IPS for port in [67, 123, 3702, 5353, 6000]]


def get_ip_version(ip: str) -> int:
    return ipaddress.ip_interface(ip).version


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

    async def get_all_used_ports(self):
        used_ports = await self.get_in_use()
        return [
            port_entry[1] for entry in used_ports for port_entry in entry['ports']
        ]

    async def get_unused_ports(self, lower_port_limit=1025):
        used_ports = set(await self.get_all_used_ports())
        return [i for i in range(lower_port_limit, 65535) if i not in used_ports]

    async def get_in_use(self):
        ports = []
        for delegate in self.DELEGATES.values():
            used_ports = await delegate.get_ports()
            if used_ports:
                for entry in used_ports:
                    entry['ports'] = [list(i) for i in entry['ports']]

                ports.append({
                    'namespace': delegate.namespace,
                    'title': delegate.title,
                    'ports': list(itertools.chain(*[entry['ports'] for entry in used_ports])),
                    'port_details': used_ports,
                })

        return ports + self.SYSTEM_USED_PORTS

    async def validate_port(self, schema, port, bindip='0.0.0.0', whitelist_namespace=None, raise_error=False):
        verrors = ValidationErrors()
        bindip_version = get_ip_version(bindip)
        wildcard_ip = '0.0.0.0' if bindip_version == 4 else '::'
        port_mapping = await self.ports_mapping(whitelist_namespace)
        port_attachment = port_mapping[port]
        if not any(
            get_ip_version(ip) == bindip_version for ip in port_attachment
        ) or (
            bindip not in port_attachment and wildcard_ip not in port_attachment and bindip != wildcard_ip
        ):
            return verrors if not raise_error else None

        ip_errors = []
        for index, port_detail in enumerate(port_attachment.items()):
            ip, port_entry = port_detail
            if get_ip_version(ip) != bindip_version:
                continue

            if bindip == wildcard_ip or ip == wildcard_ip or (bindip != wildcard_ip and ip == bindip):
                try:
                    entry = next(
                        detail for detail in port_entry['port_details']
                        if [ip, port] in detail['ports'] or [bindip, port] in detail['ports']
                    )
                    description = entry['description']
                except StopIteration:
                    description = None

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
        else:
            return verrors

    async def ports_mapping(self, whitelist_namespace=None):
        ports = defaultdict(dict)
        for attachment in filter(lambda entry: entry['namespace'] != whitelist_namespace, await self.get_in_use()):
            for bindip, port in attachment['ports']:
                ports[port][bindip] = attachment

        return ports
