import functools
from typing import Annotated, Literal
from pydantic import AfterValidator, Field, IPvAnyAddress as IPvAnyAddress_

__all__ = ["TcpPort", "Hostname", "Domain", "IPvAnyAddress", "exclude_tcp_ports"]


def _exclude_port_validation(value: int, *, ports: list[int]) -> int:
    if value in ports:
        raise ValueError(
            f'{value} is a reserved for internal use. Please select another value.'
        )
    return value


def exclude_tcp_ports(ports: list[int]):
    return functools.partial(_exclude_port_validation, ports=ports or [])


def _validate_ipaddr(address: str):
    """Return the original string instead of an ipaddress object."""
    IPvAnyAddress_(address)
    return address


TcpPort = Annotated[int, Field(ge=1, le=65535)]
Hostname = Annotated[str, Field(pattern=r'^[a-zA-Z\.\-0-9]*[a-zA-Z0-9]$')]
Domain = Annotated[str, Field(pattern=r'^[a-zA-Z\.\-0-9]*$')]
IPvAnyAddress =  Literal[''] | Annotated[str, AfterValidator(_validate_ipaddr)]
