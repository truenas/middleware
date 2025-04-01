from middlewared.api.base import BaseModel, ForUpdateMetaclass


__all__ = [
    "SystemDatasetEntry", "SystemDatasetPoolChoicesArgs", "SystemDatasetPoolChoicesResult", "SystemDatasetUpdateArgs",
    "SystemDatasetUpdateResult",
]


class SystemDatasetEntry(BaseModel):
    id: int
    pool: str
    pool_set: bool
    uuid: str
    basename: str
    path: str | None


class SystemDatasetUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    pool: str | None
    """The name of a valid pool configured in the system to host the system dataset."""
    pool_exclude: str | None
    """The name of a pool to not place the system dataset on if `pool` is not provided."""


class SystemDatasetPoolChoicesArgs(BaseModel):
    include_current_pool: bool = True
    """Include the currently set pool in the result."""


class SystemDatasetPoolChoicesResult(BaseModel):
    result: dict[str, str]
    """Names of pools that can be used for configuring system dataset."""


class SystemDatasetUpdateArgs(BaseModel):
    data: SystemDatasetUpdate


class SystemDatasetUpdateResult(BaseModel):
    result: SystemDatasetEntry
