import functools
import ipaddress
import re
from typing import Annotated, Literal

import pydantic
from pydantic import AfterValidator, Field

from ..validators import match_validator

__all__ = ["exclude_tcp_ports", "TcpPort", "Hostname", "Domain", "IPv4Address", "IPv6Address", "IPvAnyAddress",
           "IPNetwork"]


def _exclude_port_validation(value: int, *, ports: list[int]) -> int:
    if value in ports:
        raise ValueError(
            f'{value} is a reserved for internal use. Please select another value.'
        )
    return value


def exclude_tcp_ports(ports: list[int]):
    return functools.partial(_exclude_port_validation, ports=ports or [])


def _validate_ipv4_address(address: str):
    ipaddress.IPv4Address(address)
    return address


def _validate_ipv6_address(address: str):
    ipaddress.IPv6Address(address)
    return address


def _validate_ipaddr(address: str):
    """Return the original string instead of an ipaddress object."""
    pydantic.IPvAnyAddress(address)
    return address


def _validate_ip_network(network: str):
    try:
        ipaddress.IPv6Network(network)
    except Exception:
        ipaddress.IPv4Network(network)

    return network


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
IPvAnyAddress = Literal[''] | Annotated[str, AfterValidator(_validate_ipaddr)]
IPNetwork = Annotated[str, AfterValidator(_validate_ip_network)]
