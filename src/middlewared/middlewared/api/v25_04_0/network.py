from middlewared.api.base import BaseModel
from middlewared.api.v25_04_0.string_schema import IPAddr

__all__ = ["NetworkIpInUseResult", "NetworkIpInUseArgs"]

class NetworkIpInUseResultItems(BaseModel):
    type: str
    address: IPAddr
    netmask: int
    broadcast: str


class NetworkIpInUseResult(BaseModel):
    result: list[NetworkIpInUseResultItems]


class NetworkIpInUseArgs(BaseModel):
    ipv4: bool = True
    ipv6: bool = True
    ipv6_link_local: bool = False
    loopback: bool = False
    any: bool = False
    static: bool = False
