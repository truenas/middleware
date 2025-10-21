from middlewared.api.base import BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, SID
from middlewared.utils.security import STIGType
from .group import GroupEntry

__all__ = ["PrivilegeEntry", "PrivilegeRolesEntry",
           "PrivilegeCreateArgs", "PrivilegeCreateResult",
           "PrivilegeUpdateArgs", "PrivilegeUpdateResult",
           "PrivilegeDeleteArgs", "PrivilegeDeleteResult"]


class UnmappedGroupEntry(BaseModel):
    gid: int | None
    """Group ID if this is a local group that couldn't be mapped. `null` for directory service groups."""
    sid: str | None
    """Security identifier if this is a directory service group that couldn't be mapped. `null` for local groups."""
    group: None
    """Always `null` for unmapped groups."""


class PrivilegeEntry(BaseModel):
    id: int
    """Unique identifier for the privilege."""
    builtin_name: str | None
    """Name of the built-in privilege if this is a system privilege. `null` for custom privileges."""
    name: NonEmptyString
    """Display name of the privilege."""
    local_groups: list[GroupEntry | UnmappedGroupEntry]
    """Array of local groups assigned to this privilege."""
    ds_groups: list[GroupEntry | UnmappedGroupEntry]
    """Array of directory service groups assigned to this privilege."""
    roles: list[str] = []
    """Array of role names included in this privilege."""
    web_shell: bool
    """Whether this privilege grants access to the web shell."""


class PrivilegeCreate(PrivilegeEntry):
    id: Excluded = excluded_field()
    builtin_name: Excluded = excluded_field()
    local_groups: list[int] = []
    """Array of local group IDs to assign to this privilege."""
    ds_groups: list[int | SID] = []
    """Array of directory service group IDs or SIDs to assign to this privilege."""


class PrivilegeCreateArgs(BaseModel):
    privilege_create: PrivilegeCreate
    """Configuration for creating a new privilege."""


class PrivilegeCreateResult(BaseModel):
    result: PrivilegeEntry
    """The newly created privilege configuration."""


class PrivilegeUpdate(PrivilegeCreate, metaclass=ForUpdateMetaclass):
    pass


class PrivilegeUpdateArgs(BaseModel):
    id: int
    """ID of the privilege to update."""
    privilege_update: PrivilegeUpdate
    """Updated configuration for the privilege."""


class PrivilegeUpdateResult(BaseModel):
    result: PrivilegeEntry
    """The updated privilege configuration."""


class PrivilegeDeleteArgs(BaseModel):
    id: int
    """ID of the privilege to delete."""


class PrivilegeDeleteResult(BaseModel):
    result: bool
    """Whether the privilege was successfully deleted."""


class PrivilegeRolesEntry(BaseModel):
    name: NonEmptyString
    """Internal name of the role."""
    title: NonEmptyString
    """Human-readable title of the role."""
    includes: list[NonEmptyString]
    """Array of other role names that this role includes."""
    builtin: bool
    """Whether this is a built-in system role."""
    stig: STIGType | None
    """STIG compliance type for this role. `null` if not STIG-related."""
