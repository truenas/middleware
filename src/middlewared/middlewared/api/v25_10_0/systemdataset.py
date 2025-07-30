from middlewared.api.base import BaseModel, ForUpdateMetaclass


__all__ = [
    "SystemDatasetEntry", "SystemDatasetPoolChoicesArgs", "SystemDatasetPoolChoicesResult", "SystemDatasetUpdateArgs",
    "SystemDatasetUpdateResult",
]


class SystemDatasetEntry(BaseModel):
    id: int
    """Unique identifier for the system dataset configuration."""
    pool: str
    """Name of the pool hosting the system dataset."""
    pool_set: bool
    """Whether a pool has been explicitly set for the system dataset."""
    uuid: str
    """UUID of the system dataset."""
    basename: str
    """Base name of the system dataset."""
    path: str | None
    """Filesystem path to the system dataset. `null` if not mounted."""


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
    """Updated configuration for the system dataset."""


class SystemDatasetUpdateResult(BaseModel):
    result: SystemDatasetEntry
    """The updated system dataset configuration."""
