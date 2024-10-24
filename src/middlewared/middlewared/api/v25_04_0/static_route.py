from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass

from pydantic import IPvAnyAddress, IPvAnyNetwork


__all__ = [
    "StaticRouteEntry",
    "StaticRouteUpdateArgs",
    "StaticRouteUpdateResult",
    "StaticRouteCreateArgs",
    "StaticRouteCreateResult",
    "StaticRouteDeleteArgs",
    "StaticRouteDeleteResult",
]


class StaticRouteEntry(BaseModel):
    destination: IPvAnyNetwork
    gateway: IPvAnyAddress
    description: str = ""
    id: int


class StaticRouteCreate(StaticRouteEntry):
    id: Excluded = excluded_field()


class StaticRouteCreateArgs(BaseModel):
    data: StaticRouteCreate


class StaticRouteCreateResult(BaseModel):
    result: StaticRouteEntry


class StaticRouteUpdate(StaticRouteEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class StaticRouteUpdateArgs(BaseModel):
    id: int
    data: StaticRouteUpdate


class StaticRouteUpdateResult(BaseModel):
    result: StaticRouteEntry


class StaticRouteDeleteArgs(BaseModel):
    id: int


class StaticRouteDeleteResult(BaseModel):
    result: bool
