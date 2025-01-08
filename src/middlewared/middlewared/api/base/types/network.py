import functools
from typing import Annotated
from pydantic import Field

__all__ = ["TcpPort", "exclude_tcp_ports"]


def _exclude_port_validation(value: int, *, ports: list[int]) -> int:
    if value in ports:
        raise ValueError(
            f'{value} is a reserved for internal use. Please select another value.'
        )
    return value


def exclude_tcp_ports(ports: list[int]):
    return functools.partial(_exclude_port_validation, ports=ports or [])


TcpPort = Annotated[int, Field(ge=1, le=65535)]
