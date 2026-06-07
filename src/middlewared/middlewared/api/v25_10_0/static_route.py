from pydantic import Field, IPvAnyAddress, IPvAnyNetwork

from middlewared.api.base import BaseModel, Excluded, ForUpdateMetaclass, NonEmptyString, excluded_field

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
    destination: NonEmptyString = Field(description="Destination network or host for this static route.")
    gateway: NonEmptyString = Field(description="Gateway IP address for this static route.")
    description: str = Field(default="", description="Optional description for this static route.")
    id: int = Field(description="Unique identifier for this static route.")


class StaticRouteCreate(StaticRouteEntry):
    id: Excluded = excluded_field()
    destination: IPvAnyNetwork = Field(description="Destination network (CIDR notation) for this static route.")
    gateway: IPvAnyAddress = Field(description="Gateway IP address for this static route.")


class StaticRouteCreateArgs(BaseModel):
    data: StaticRouteCreate = Field(description="Configuration for the new static route.")


class StaticRouteCreateResult(BaseModel):
    result: StaticRouteEntry = Field(description="The newly created static route configuration.")


class StaticRouteUpdate(StaticRouteCreate, metaclass=ForUpdateMetaclass):
    pass


class StaticRouteUpdateArgs(BaseModel):
    id: int = Field(description="ID of the static route to update.")
    data: StaticRouteUpdate = Field(description="Updated configuration for the static route.")


class StaticRouteUpdateResult(BaseModel):
    result: StaticRouteEntry = Field(description="The updated static route configuration.")


class StaticRouteDeleteArgs(BaseModel):
    id: int = Field(description="ID of the static route to delete.")


class StaticRouteDeleteResult(BaseModel):
    result: bool = Field(description="Whether the static route was successfully deleted.")
