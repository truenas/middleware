from pydantic import Field

from middlewared.api.base import BaseModel

__all__ = [
    "ZPoolOffline",
    "ZPoolOfflineArgs",
    "ZPoolOfflineResult",
    "ZPoolOnline",
    "ZPoolOnlineArgs",
    "ZPoolOnlineResult",
]


class ZPoolOffline(BaseModel):
    pool_name: str = Field(description="Name of the zpool.")
    vdev_guid: str = Field(
        description="GUID of the disk to take offline: the `guid` that `zpool.query` reports for it in `topology`, "
        "as a decimal string."
    )


class ZPoolOfflineArgs(BaseModel):
    data: ZPoolOffline = Field(description="Disk to take offline.")


class ZPoolOfflineResult(BaseModel):
    result: None


class ZPoolOnline(BaseModel):
    pool_name: str = Field(description="Name of the zpool.")
    vdev_guid: str = Field(
        description="GUID of the disk to bring online: the `guid` that `zpool.query` reports for it in `topology`, "
        "as a decimal string."
    )


class ZPoolOnlineArgs(BaseModel):
    data: ZPoolOnline = Field(description="Disk to bring online.")


class ZPoolOnlineResult(BaseModel):
    result: None
