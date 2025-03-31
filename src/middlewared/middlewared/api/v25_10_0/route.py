from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["RouteSystemRoutesItem", "RouteIPv4gwReachableArgs", "RouteIPv4gwReachableResult",]


class RouteSystemRoutesItem(BaseModel):
    network: IPvAnyAddress
    netmask: IPvAnyAddress
    gateway: IPvAnyAddress | None
    interface: str
    flags: list
    table_id: int
    scope: int
    preferred_source: str | None


class RouteIPv4gwReachableArgs(BaseModel):
    ipv4_gateway: str


class RouteIPv4gwReachableResult(BaseModel):
    result: bool
