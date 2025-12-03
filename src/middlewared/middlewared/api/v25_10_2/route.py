from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["RouteSystemRoutesItem", "RouteIpv4gwReachableArgs", "RouteIpv4gwReachableResult",]


class RouteSystemRoutesItem(BaseModel):
    network: IPvAnyAddress
    """Network address for this route."""
    netmask: IPvAnyAddress
    """Network mask for this route."""
    gateway: IPvAnyAddress | None
    """Gateway IP address for this route. `null` if directly connected."""
    interface: str | None
    """Network interface name for this route. `null` if not bound to specific interface."""
    flags: list
    """Array of routing flags for this route."""
    table_id: int
    """Routing table ID where this route is stored."""
    scope: int
    """Routing scope indicating the distance to the destination."""
    preferred_source: str | None
    """Preferred source IP address for outgoing packets. `null` if not specified."""


class RouteIpv4gwReachableArgs(BaseModel):
    ipv4_gateway: str
    """IPv4 gateway address to test for reachability."""


class RouteIpv4gwReachableResult(BaseModel):
    result: bool
    """Whether the specified IPv4 gateway is reachable."""
