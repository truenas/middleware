from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass

__all__ = [
    "SystemDatasetEntry", "SystemDatasetPoolChoicesArgs", "SystemDatasetPoolChoicesResult", "SystemDatasetUpdateArgs",
    "SystemDatasetUpdateResult",
]


class SystemDatasetEntry(BaseModel):
    id: int = Field(description="Unique identifier for the system dataset configuration.")
    pool: str = Field(description="Name of the pool hosting the system dataset.")
    pool_set: bool = Field(description="Whether a pool has been explicitly set for the system dataset.")
    uuid: str = Field(description="UUID of the system dataset.")
    basename: str = Field(description="Base name of the system dataset.")
    path: str | None = Field(description="Filesystem path to the system dataset. `null` if not mounted.")


class SystemDatasetUpdate(BaseModel, metaclass=ForUpdateMetaclass):
    pool: str | None = Field(
        description="The name of a valid pool configured in the system to host the system dataset.",
    )
    pool_exclude: str | None = Field(
        description="The name of a pool to not place the system dataset on if `pool` is not provided.",
    )


class SystemDatasetPoolChoicesArgs(BaseModel):
    include_current_pool: bool = Field(default=True, description="Include the currently set pool in the result.")


class SystemDatasetPoolChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Names of pools that can be used for configuring system dataset.")


class SystemDatasetUpdateArgs(BaseModel):
    data: SystemDatasetUpdate = Field(description="Updated configuration for the system dataset.")


class SystemDatasetUpdateResult(BaseModel):
    result: SystemDatasetEntry = Field(description="The updated system dataset configuration.")
