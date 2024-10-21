from middlewared.api.base import BaseModel
from middlewared.api.v25_04_0.string_schema import IPAddr

__all__ = ["NetworkIpInUseResult", "NetworkIpInUseArgs", "NetworkIpInUseResultItem",
    "NetworkGeneralSummaryArgs", "NetworkGeneralSummaryResultEntry", "NetworkGeneralSummaryResult"]

class NetworkIpInUseResultItem(BaseModel):
    type: str
    address: IPAddr
    netmask: int
    broadcast: str


class NetworkIpInUseResult(BaseModel):
    result: list[NetworkIpInUseResultItem]


class NetworkIpInUseArgs(BaseModel):
    ipv4: bool = True
    ipv6: bool = True
    ipv6_link_local: bool = False
    loopback: bool = False
    any: bool = False
    static: bool = False

class NetworkGeneralSummaryArgs(BaseModel):
    pass

class NetworkGeneralSummaryResultEntry(BaseModel):
    ips: dict
    default_route: list[IPAddr]
    nameservers: list[IPAddr]

class NetworkGeneralSummaryResult(BaseModel):
    result: NetworkGeneralSummaryResultEntry
