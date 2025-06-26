from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, SID
from middlewared.utils.security import STIGType
from .group import GroupEntry

__all__ = ["PrivilegeEntry", "PrivilegeRolesEntry",
           "PrivilegeCreateArgs", "PrivilegeCreateResult",
           "PrivilegeUpdateArgs", "PrivilegeUpdateResult",
           "PrivilegeDeleteArgs", "PrivilegeDeleteResult"]


class UnmappedGroupEntry(BaseModel):
    gid: int | None
    sid: str | None
    group: None


class PrivilegeEntry(BaseModel):
    id: int
    builtin_name: str | None
    name: NonEmptyString
    local_groups: list[GroupEntry | UnmappedGroupEntry]
    ds_groups: list[GroupEntry | UnmappedGroupEntry]
    roles: list[str] = []
    web_shell: bool


class PrivilegeCreate(PrivilegeEntry):
    id: Excluded = excluded_field()
    builtin_name: Excluded = excluded_field()
    local_groups: list[int] = []
    ds_groups: list[int | SID] = []


class PrivilegeCreateArgs(BaseModel):
    privilege_create: PrivilegeCreate


class PrivilegeCreateResult(BaseModel):
    result: PrivilegeEntry


class PrivilegeUpdate(PrivilegeCreate, metaclass=ForUpdateMetaclass):
    pass


class PrivilegeUpdateArgs(BaseModel):
    id: int
    privilege_update: PrivilegeUpdate


class PrivilegeUpdateResult(BaseModel):
    result: PrivilegeEntry


class PrivilegeDeleteArgs(BaseModel):
    id: int


class PrivilegeDeleteResult(BaseModel):
    result: bool


class PrivilegeRolesEntry(BaseModel):
    name: NonEmptyString
    title: NonEmptyString
    includes: list[NonEmptyString]
    builtin: bool
    stig: STIGType | None
