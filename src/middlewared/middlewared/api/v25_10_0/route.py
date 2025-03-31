from middlewared.api.base import BaseModel, IPvAnyAddress


__all__ = ["RouteSystemRoutes", "RouteIPv4gwReachableArgs", "RouteIPv4gwReachableResult",]


class RouteSystemRoutes(BaseModel):
    network: IPvAnyAddress
    netmask: IPvAnyAddress
    gateway: IPvAnyAddress | None
    interface: str | None
    flags: list
    table_id: int
    scope: int
    preferred_source: str | None


class RouteIPv4gwReachableArgs(BaseModel):
    ipv4_gateway: str


class RouteIPv4gwReachableResult(BaseModel):
    result: bool
