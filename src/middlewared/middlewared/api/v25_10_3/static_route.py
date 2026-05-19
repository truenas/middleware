from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString


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
    """Destination network or host for this static route."""
    gateway: NonEmptyString
    """Gateway IP address for this static route."""
    description: str = ""
    """Optional description for this static route."""
    id: int
    """Unique identifier for this static route."""


class StaticRouteCreate(StaticRouteEntry):
    id: Excluded = excluded_field()


class StaticRouteCreateArgs(BaseModel):
    data: StaticRouteCreate
    """Configuration for the new static route."""


class StaticRouteCreateResult(BaseModel):
    result: StaticRouteEntry
    """The newly created static route configuration."""


class StaticRouteUpdate(StaticRouteCreate, metaclass=ForUpdateMetaclass):
    pass


class StaticRouteUpdateArgs(BaseModel):
    id: int
    """ID of the static route to update."""
    data: StaticRouteUpdate
    """Updated configuration for the static route."""


class StaticRouteUpdateResult(BaseModel):
    result: StaticRouteEntry
    """The updated static route configuration."""


class StaticRouteDeleteArgs(BaseModel):
    id: int
    """ID of the static route to delete."""


class StaticRouteDeleteResult(BaseModel):
    result: bool
    """Whether the static route was successfully deleted."""
