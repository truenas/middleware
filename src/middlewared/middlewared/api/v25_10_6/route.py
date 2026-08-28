from pydantic import Field

from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["RouteSystemRoutesItem", "RouteIpv4gwReachableArgs", "RouteIpv4gwReachableResult",]


class RouteSystemRoutesItem(BaseModel):
    network: IPvAnyAddress = Field(description="Network address for this route.")
    netmask: IPvAnyAddress = Field(description="Network mask for this route.")
    gateway: IPvAnyAddress | None = Field(
        description="Gateway IP address for this route. `null` if directly connected.",
    )
    interface: str | None = Field(
        description="Network interface name for this route. `null` if not bound to specific interface.",
    )
    flags: list = Field(description="Array of routing flags for this route.")
    table_id: int = Field(description="Routing table ID where this route is stored.")
    scope: int = Field(description="Routing scope indicating the distance to the destination.")
    preferred_source: str | None = Field(
        description="Preferred source IP address for outgoing packets. `null` if not specified.",
    )


class RouteIpv4gwReachableArgs(BaseModel):
    ipv4_gateway: str = Field(description="IPv4 gateway address to test for reachability.")


class RouteIpv4gwReachableResult(BaseModel):
    result: bool = Field(description="Whether the specified IPv4 gateway is reachable.")
