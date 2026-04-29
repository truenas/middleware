from __future__ import annotations

from collections import defaultdict
import itertools
from typing import Any

from middlewared.common.ports import PortDelegate, PortEntry
from middlewared.service import ValidationErrors

from .utils import SYSTEM_PORTS, get_ip_version

DELEGATES: dict[str, PortDelegate] = {}

SYSTEM_USED_PORTS: list[dict[str, Any]] = [
    {
        "title": "System",
        "ports": SYSTEM_PORTS,
        "port_details": [{"description": None, "ports": SYSTEM_PORTS}],
        "namespace": "system",
    },
]


def register_attachment_delegate(delegate: PortDelegate) -> None:
    if delegate.namespace in DELEGATES:
        raise ValueError(f"{delegate.namespace!r} delegate is already registered with Port Service")
    DELEGATES[delegate.namespace] = delegate


async def get_in_use() -> list[dict[str, Any]]:
    ports: list[dict[str, Any]] = []
    for delegate in DELEGATES.values():
        used_ports = await delegate.get_ports()
        if used_ports:
            for entry in used_ports:
                entry["ports"] = [list(i) for i in entry["ports"]]  # type: ignore[misc]

            ports.append({
                "namespace": delegate.namespace,
                "title": delegate.title,
                "ports": list(itertools.chain(*[entry["ports"] for entry in used_ports])),
                "port_details": used_ports,
            })

    return ports + SYSTEM_USED_PORTS


async def get_all_used_ports() -> list[int]:
    used_ports = await get_in_use()
    return [
        port_entry[1] for entry in used_ports for port_entry in entry["ports"]
    ]


async def get_unused_ports(lower_port_limit: int = 1025) -> list[int]:
    used_ports = set(await get_all_used_ports())
    return [i for i in range(lower_port_limit, 65535) if i not in used_ports]


async def ports_mapping(whitelist_namespace: str | None = None) -> defaultdict[int, dict[str, Any]]:
    ports: defaultdict[int, dict[str, Any]] = defaultdict(dict)
    for attachment in filter(lambda entry: entry["namespace"] != whitelist_namespace, await get_in_use()):
        for bindip, port in attachment["ports"]:
            ports[port][bindip] = attachment

    return ports


def _validate_single_port(
    schema: str,
    port: int,
    bindip: str,
    port_mapping: defaultdict[int, dict[str, Any]],
) -> ValidationErrors:
    """Validate a single port/bindip against a pre-computed port mapping.

    Returns a ValidationErrors object (empty if no conflict found).
    """
    verrors = ValidationErrors()
    bindip_version = get_ip_version(bindip)
    wildcard_ip = "0.0.0.0" if bindip_version == 4 else "::"
    port_attachment = port_mapping[port]
    if not any(
        get_ip_version(ip) == bindip_version for ip in port_attachment
    ) or (
        bindip not in port_attachment and wildcard_ip not in port_attachment and bindip != wildcard_ip
    ):
        return verrors

    ip_errors: list[str] = []
    for index, port_detail in enumerate(port_attachment.items()):
        ip, port_entry = port_detail
        if get_ip_version(ip) != bindip_version:
            continue

        if bindip == wildcard_ip or ip == wildcard_ip or (bindip != wildcard_ip and ip == bindip):
            try:
                entry = next(
                    detail for detail in port_entry["port_details"]
                    if [ip, port] in detail["ports"] or [bindip, port] in detail["ports"]
                )
                description = entry["description"]
            except StopIteration:
                description = None

            ip_errors.append(
                f'{index + 1}) "{ip}:{port}" used by {port_entry["title"]}'
                f'{f" ({description})" if description else ""}'
            )

    err = "\n".join(ip_errors)
    verrors.add(
        schema,
        f"The port is being used by following services:\n{err}"
    )

    return verrors


async def validate_port(
    schema: str,
    port: int,
    bindip: str = "0.0.0.0",
    whitelist_namespace: str | None = None,
    raise_error: bool = False,
) -> ValidationErrors | None:
    """Validate whether a single port/bindip combination is available.

    When raise_error is True, raises ValidationErrors if the port conflicts
    and returns None otherwise. When False, returns a ValidationErrors object
    (which may be empty if no conflict).
    """
    port_mapping = await ports_mapping(whitelist_namespace)
    verrors = _validate_single_port(schema, port, bindip, port_mapping)
    if raise_error:
        verrors.check()
        return None
    else:
        return verrors


async def validate_ports(
    schema: str,
    ports: list[PortEntry],
    whitelist_namespace: str | None = None,
    raise_error: bool = False,
) -> list[tuple[str, str, int]] | None:
    """Validate multiple port/bindip combinations in a single call.

    Calls ports_mapping() once and checks all entries against it.
    Each entry is a dict with a required 'port' key and an optional
    'bindip' key (defaults to '0.0.0.0').

    When raise_error is True, raises a single ValidationErrors containing
    all conflicts and returns None if there are none. When False, returns
    a JSON-serializable list of (attribute, errmsg, errno) tuples.
    """
    port_mapping = await ports_mapping(whitelist_namespace)
    all_verrors = ValidationErrors()
    for entry in ports:
        verrors = _validate_single_port(schema, entry["port"], entry.get("bindip", "0.0.0.0"), port_mapping)
        all_verrors.extend(verrors)

    if raise_error:
        all_verrors.check()
        return None
    else:
        return list(all_verrors)
