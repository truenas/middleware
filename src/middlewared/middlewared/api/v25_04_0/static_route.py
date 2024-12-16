from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString

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
    destination: NonEmptyString
    gateway: NonEmptyString
    description: str = ""
    id: int


class StaticRouteCreate(StaticRouteEntry):
    id: Excluded = excluded_field()
    destination: IPvAnyNetwork
    gateway: IPvAnyAddress


class StaticRouteCreateArgs(BaseModel):
    data: StaticRouteCreate


class StaticRouteCreateResult(BaseModel):
    result: StaticRouteEntry


class StaticRouteUpdate(StaticRouteCreate, metaclass=ForUpdateMetaclass):
    pass


class StaticRouteUpdateArgs(BaseModel):
    id: int
    data: StaticRouteUpdate


class StaticRouteUpdateResult(BaseModel):
    result: StaticRouteEntry


class StaticRouteDeleteArgs(BaseModel):
    id: int


class StaticRouteDeleteResult(BaseModel):
    result: bool
