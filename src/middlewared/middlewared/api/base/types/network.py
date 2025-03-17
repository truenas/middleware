import functools
import re
from typing import Annotated, Literal
from pydantic import AfterValidator, Field, IPvAnyAddress as IPvAnyAddress_
from ..validators import match_validator

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
Hostname = Annotated[str, AfterValidator(match_validator(
    re.compile(r"^[a-z\.\-0-9]*[a-z0-9]$", re.IGNORECASE),
    "Hostname can only contain letters, numbers, periods, and dashes and must end with a letter or number"
))]
Domain = Annotated[str, AfterValidator(match_validator(
    re.compile(r"^[a-z\.\-0-9]*$", re.IGNORECASE),
    "Domain can only contain letters, numbers, periods, and dashes"
))]
IPvAnyAddress =  Literal[''] | Annotated[str, AfterValidator(_validate_ipaddr)]
