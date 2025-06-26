from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, ContainerXID, Excluded, excluded_field, ForUpdateMetaclass, LocalUID, GroupName, NonEmptyString,
    single_argument_args, single_argument_result
)

__all__ = ["GroupEntry",
           "GroupCreateArgs", "GroupCreateResult",
           "GroupUpdateArgs", "GroupUpdateResult",
           "GroupDeleteArgs", "GroupDeleteResult",
           "GroupGetNextGidArgs", "GroupGetNextGidResult",
           "GroupGetGroupObjArgs", "GroupGetGroupObjResult",
           "GroupHasPasswordEnabledUserArgs", "GroupHasPasswordEnabledUserResult"]


class GroupEntry(BaseModel):
    id: int
    """ This is the API identifier for the group. Use this ID for `group.update` and `group.delete` API calls. This ID
    also appears in the `groups` array for each user entry in `user.query` results.

    NOTE: For groups from a directory service, the `id` is calculated by adding 100000000 to the `gid`. This ensures
    consistent API results. You cannot change directory service accounts through TrueNAS. """
    gid: int
    """ A non-negative integer used to identify a group. TrueNAS uses this value for permission checks and many other
    system purposes. """
    name: NonEmptyString
    """ A string used to identify a group."""
    builtin: bool
    """ If `True`, the group is an internal system account for the TrueNAS server. Typically, one should
    create dedicated groups for access to the TrueNAS server webui and shares. """
    sudo_commands: list[NonEmptyString] = []
    """ A list of commands that group members may execute with elevated privileges. User is prompted for password
    when executing any command from the list. """
    sudo_commands_nopasswd: list[NonEmptyString] = []
    """ A list of commands that group members may execute with elevated privileges. User is not prompted for password
    when executing any command from the list. """
    smb: bool = True
    """ If set to `True`, the group can be used for SMB share ACL entries. The group is mapped to an NT group account
    on the TrueNAS SMB server and has a `sid` value. """
    userns_idmap: Literal['DIRECT'] | ContainerXID | None = None
    """
    Specifies the subgid mapping for this group. If DIRECT then the GID will be \
    directly mapped to all containers. Alternatively, the target GID may be \
    explicitly specified. If None, then the GID will not be mapped.

    **NOTE: This field will be ignored for groups that have been assigned TrueNAS roles.**
    """
    group: NonEmptyString
    """ A string used to identify a group. Identical to the `name` key. """
    local: bool
    """ If `True`, the group is local to the TrueNAS server. If `False`, the group is provided by a directory service. """
    sid: str | None
    """ The Security Identifier (SID) of the user if the account an `smb` account. The SMB server uses this value to
    check share access and for other purposes. """
    roles: list[str]
    """ List of roles assigned to this groups. Roles control administrative access to TrueNAS through the web UI and
    API. You can change group roles by using `privilege.create`, `privilege.update`, and `privilege.delete`. """
    users: list[int] = []
    """ A list a API user identifiers for local users who are members of this group. These IDs match the `id` field
    from `user.query`.

    NOTE: this field is empty for groups that come from directory services (`local` is `False`). """


class GroupCreate(GroupEntry):
    id: Excluded = excluded_field()
    builtin: Excluded = excluded_field()
    group: Excluded = excluded_field()
    local: Excluded = excluded_field()
    sid: Excluded = excluded_field()
    roles: Excluded = excluded_field()

    gid: LocalUID | None = None
    """If `null`, it is automatically filled with the next one available."""
    name: GroupName


class GroupCreateArgs(BaseModel):
    group_create: GroupCreate


class GroupCreateResult(BaseModel):
    result: int


class GroupUpdate(GroupCreate, metaclass=ForUpdateMetaclass):
    gid: Excluded = excluded_field()


class GroupUpdateArgs(BaseModel):
    id: int
    group_update: GroupUpdate


class GroupUpdateResult(BaseModel):
    result: int


class GroupDeleteOptions(BaseModel):
    delete_users: bool = False
    """Deletes all users that have this group as their primary group."""


class GroupDeleteArgs(BaseModel):
    id: int
    options: GroupDeleteOptions = Field(default=GroupDeleteOptions())


class GroupDeleteResult(BaseModel):
    result: int


class GroupGetNextGidArgs(BaseModel):
    pass


class GroupGetNextGidResult(BaseModel):
    result: int


@single_argument_args("get_group_obj")
class GroupGetGroupObjArgs(BaseModel):
    groupname: str | None = None
    gid: int | None = None
    sid_info: bool = False


@single_argument_result
class GroupGetGroupObjResult(BaseModel):
    gr_name: str
    """Name of the group."""
    gr_gid: int
    """Group ID of the group."""
    gr_mem: list[str]
    """List of group names that are members of the group."""
    sid: str | None = None
    """Optional SID value for the account that is present if `sid_info` is specified in payload."""
    source: Literal['LOCAL', 'ACTIVEDIRECTORY', 'LDAP']
    """
    The name server switch module that provided the user. Options are:

    * FILES: Local user in passwd file of server.
    * WINBIND: User provided by winbindd.
    * SSS: User provided by SSSD.
    """
    local: bool
    """This group is local to the NAS or provided by a directory service."""


class GroupHasPasswordEnabledUserArgs(BaseModel):
    gids: list[int]
    exclude_user_ids: list[int] = []


class GroupHasPasswordEnabledUserResult(BaseModel):
    result: bool
