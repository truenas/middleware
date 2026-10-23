from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field

from middlewared.api.base import BaseModel, NonEmptyString, UniqueList, ZFSSpaceLimit

__all__ = (
    "ZFSResourceUserspaceQuery",
    "ZFSResourceUserspaceEntry",
    "ZFSResourceUserspaceListArgs",
    "ZFSResourceUserspaceListResult",
    "ZFSResourceUserspaceQuota",
    "ZFSResourceUserspaceSetArgsData",
    "ZFSResourceUserspaceSetArgs",
    "ZFSResourceUserspaceSetResult",
)


UserspaceType = Literal["user", "group", "project"]


def _obj_quota(value: Any) -> Any:
    if value == "none":
        return 0
    return value


ObjQuota = Annotated[int, BeforeValidator(_obj_quota), Field(ge=0)]


class ZFSResourceUserspaceQuery(BaseModel):
    paths: UniqueList[NonEmptyString] = Field(
        min_length=1,
        description=(
            "Filesystem paths to read. A path that does not exist is skipped. An internal path is read when it is "
            "named here."
        ),
    )
    types: UniqueList[UserspaceType] = Field(
        min_length=1,
        description="Kinds of userspace accounting to read: per user, per group or per project.",
    )


class ZFSResourceUserspaceEntry(BaseModel):
    dataset: str = Field(description="Path of the filesystem the row belongs to.")
    type: UserspaceType = Field(description="Whether `xid` is a user, group or project id.")
    xid: int = Field(description="The numeric user, group or project id. Names are not resolved.")
    used: int = Field(description="Bytes charged to `xid`. 0 means none.")
    quota: int = Field(description="Space limit of `xid` in bytes. 0 means no limit.")
    objused: int = Field(description="Number of objects charged to `xid`. 0 means none.")
    objquota: int = Field(description="Object count limit of `xid`. 0 means no limit.")


class ZFSResourceUserspaceListArgs(BaseModel):
    data: ZFSResourceUserspaceQuery = Field(description="Which filesystems and kinds of accounting to read.")


class ZFSResourceUserspaceListResult(BaseModel):
    result: list[ZFSResourceUserspaceEntry]


class ZFSResourceUserspaceQuota(BaseModel):
    type: UserspaceType = Field(description="Whether `xid` is a user, group or project id.")
    xid: int = Field(ge=0, le=4294967295, description="The numeric user, group or project id.")
    quota: ZFSSpaceLimit | None = Field(
        default=None,
        description=(
            "Space limit, as a byte count or a size string such as '10G'. 0 or 'none' removes the limit. Null leaves "
            "it unchanged."
        ),
    )
    objquota: ObjQuota | None = Field(
        default=None,
        description="Object count limit. 0 or 'none' removes the limit. Null leaves it unchanged.",
    )


class ZFSResourceUserspaceSetArgsData(BaseModel):
    path: NonEmptyString = Field(description="Path of the filesystem to change. Snapshot paths are not accepted.")
    quotas: list[ZFSResourceUserspaceQuota] = Field(
        min_length=1,
        description="Limits to write. Each entry must set `quota`, `objquota` or both.",
    )


class ZFSResourceUserspaceSetArgs(BaseModel):
    data: ZFSResourceUserspaceSetArgsData = Field(description="The filesystem and the limits to write to it.")


class ZFSResourceUserspaceSetResult(BaseModel):
    result: None
