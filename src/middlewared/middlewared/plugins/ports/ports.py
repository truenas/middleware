from __future__ import annotations

import itertools
from collections import defaultdict
from typing import Any

from middlewared.common.ports import PortDelegate
from middlewared.service import ValidationErrors

from .utils import SYSTEM_PORTS, get_ip_version

DELEGATES: dict[str, PortDelegate] = {}

SYSTEM_USED_PORTS: list[dict[str, Any]] = [
    {
        'title': 'System',
        'ports': SYSTEM_PORTS,
        'port_details': [{'description': None, 'ports': SYSTEM_PORTS}],
        'namespace': 'system',
    },
]


def register_attachment_delegate(delegate: PortDelegate) -> None:
    if delegate.namespace in DELEGATES:
        raise ValueError(f'{delegate.namespace!r} delegate is already registered with Port Service')
    DELEGATES[delegate.namespace] = delegate


async def get_in_use() -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    for delegate in DELEGATES.values():
        used_ports = await delegate.get_ports()
        if used_ports:
            for entry in used_ports:
                entry['ports'] = [list(i) for i in entry['ports']]  # type: ignore[misc]

            ports.append({
                'namespace': delegate.namespace,
                'title': delegate.title,
                'ports': list(itertools.chain(*[entry['ports'] for entry in used_ports])),
                'port_details': used_ports,
            })

    return ports + SYSTEM_USED_PORTS


async def get_all_used_ports() -> list[int]:
    used_ports = await get_in_use()
    return [
        port_entry[1] for entry in used_ports for port_entry in entry['ports']
    ]


async def get_unused_ports(lower_port_limit: int = 1025) -> list[int]:
    used_ports = set(await get_all_used_ports())
    return [i for i in range(lower_port_limit, 65535) if i not in used_ports]


async def ports_mapping(whitelist_namespace: str | None = None) -> defaultdict[int, dict[str, Any]]:
    ports: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    for attachment in filter(lambda entry: entry['namespace'] != whitelist_namespace, await get_in_use()):
        for bindip, port in attachment['ports']:
            ports[port][bindip] = attachment

    return ports


async def validate_port(
    schema: str,
    port: int,
    bindip: str = '0.0.0.0',
    whitelist_namespace: str | None = None,
    raise_error: bool = False,
) -> ValidationErrors | None:
    verrors = ValidationErrors()
    bindip_version = get_ip_version(bindip)
    wildcard_ip = '0.0.0.0' if bindip_version == 4 else '::'
    port_mapping = await ports_mapping(whitelist_namespace)
    port_attachment = port_mapping[port]
    if not any(
        get_ip_version(ip) == bindip_version for ip in port_attachment
    ) or (
        bindip not in port_attachment and wildcard_ip not in port_attachment and bindip != wildcard_ip
    ):
        return verrors if not raise_error else None

    ip_errors: list[str] = []
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
        return None
    else:
        return verrors
