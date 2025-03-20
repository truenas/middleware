import functools
import ipaddress
import re
from typing import Annotated, Literal

import pydantic
from pydantic import AfterValidator, Field

from ..validators import match_validator

__all__ = [
    "exclude_tcp_ports", "TcpPort", "Hostname", "Domain", "IPv4Address", "IPv6Address",
    "IPvAnyAddress", "IPNetwork", "NameserverAddress",
]


def _exclude_port_validation(value: int, *, ports: list[int]) -> int:
    if value in ports:
        raise ValueError(
            f'{value} is a reserved for internal use. Please select another value.'
        )
    return value


def exclude_tcp_ports(ports: list[int]):
    """Validate that an integer is not in the given set `ports`."""
    return functools.partial(_exclude_port_validation, ports=ports or [])


def _validate_ipv4_address(address: str):
    """Return the original string instead of an ipaddress object."""
    ipaddress.IPv4Address(address)
    return address


def _validate_ipv6_address(address: str):
    """Return the original string instead of an ipaddress object."""
    ipaddress.IPv6Address(address)
    return address


def _validate_ip_address(address: str):
    """Return the original string instead of an ipaddress object."""
    pydantic.IPvAnyAddress(address)
    return address


def _validate_ip_network(network: str):
    """Return the original string instead of an ipaddress object."""
    pydantic.IPvAnyNetwork(network)
    return network


def _validate_nameserver(address: str):
    """Validate that an IP address can be the address of a nameserver."""
    nameserver = pydantic.IPvAnyAddress(address)
    error = None

    if nameserver.is_loopback:
        error = 'Loopback is not a valid nameserver'
    elif nameserver.is_unspecified:
        error = 'Unspecified addresses are not valid as nameservers'
    elif nameserver.version == 4:
        if address == '255.255.255.255':
            error = 'This is not a valid nameserver address'
        elif address.startswith('169.254'):
            error = '169.254/16 subnet is not valid for nameserver'

    if error:
        raise ValueError(error)

    return address


TcpPort = Annotated[int, Field(ge=1, le=65535)]
Hostname = Annotated[str, AfterValidator(match_validator(
    re.compile(r"^[a-z.\-0-9]*[a-z0-9]$", re.IGNORECASE),
    "Hostname can only contain letters, numbers, periods, and dashes and must end with a letter or number"
))]
Domain = Annotated[str, AfterValidator(match_validator(
    re.compile(r"^[a-z.\-0-9]*$", re.IGNORECASE),
    "Domain can only contain letters, numbers, periods, and dashes"
))]
IPv4Address = Annotated[str, AfterValidator(_validate_ipv4_address)]
IPv6Address = Annotated[str, AfterValidator(_validate_ipv6_address)]
IPvAnyAddress = Literal[''] | Annotated[str, AfterValidator(_validate_ip_address)]
IPNetwork = Annotated[str, AfterValidator(_validate_ip_network)]
NameserverAddress = Annotated[str, AfterValidator(_validate_nameserver)]
