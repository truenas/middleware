from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["RouteSystemRoutesItem", "RouteIpv4gwReachableArgs", "RouteIpv4gwReachableResult",]


class RouteSystemRoutesItem(BaseModel):
    network: IPvAnyAddress
    netmask: IPvAnyAddress
    gateway: IPvAnyAddress | None
    interface: str | None
    flags: list
    table_id: int
    scope: int
    preferred_source: str | None


class RouteIpv4gwReachableArgs(BaseModel):
    ipv4_gateway: str


class RouteIpv4gwReachableResult(BaseModel):
    result: bool
