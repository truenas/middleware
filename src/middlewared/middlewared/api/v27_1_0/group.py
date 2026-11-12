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
    id: int = Field(
        description=(
            "This is the API identifier for the group. Use this ID for `group.update` and `group.delete` API calls. "
            "This ID also appears in the `groups` array for each user entry in `user.query` results.\n"
            "\n"
            "NOTE: For groups from a directory service, the `id` is calculated by adding 100000000 to the `gid`. This "
            "ensures consistent API results. You cannot change directory service accounts through TrueNAS."
        ),
    )
    gid: int = Field(
        description=(
            "A non-negative integer used to identify a group. TrueNAS uses this value for permission checks and many "
            "other system purposes."
        ),
    )
    name: NonEmptyString = Field(description="A string used to identify a group.")
    builtin: bool = Field(
        description=(
            "If `True`, the group is an internal system account for the TrueNAS server. Typically, one should create "
            "dedicated groups for access to the TrueNAS server webui and shares."
        ),
    )
    sudo_commands: list[NonEmptyString] = Field(
        default=[],
        description=(
            "A list of commands that group members may execute with elevated privileges. User is prompted for password "
            "when executing any command from the list."
        ),
    )
    sudo_commands_nopasswd: list[NonEmptyString] = Field(
        default=[],
        description=(
            "A list of commands that group members may execute with elevated privileges. User is not prompted for "
            "password when executing any command from the list."
        ),
    )
    smb: bool = Field(
        default=True,
        description=(
            "If set to `True`, the group can be used for SMB share ACL entries. The group is mapped to an NT group "
            "account on the TrueNAS SMB server and has a `sid` value."
        ),
    )
    userns_idmap: Literal['DIRECT'] | ContainerXID | None = Field(
        default=None,
        description=(
            "Specifies the subgid mapping for this group. If DIRECT then the GID will be directly mapped to all "
            "containers. Alternatively, the target GID may be explicitly specified. If null, then the GID will not be "
            "mapped.\n"
            "\n"
            "**NOTE: This field will be ignored for groups that have been assigned TrueNAS roles.**"
        ),
    )
    group: NonEmptyString = Field(description="A string used to identify a group. Identical to the `name` key.")
    local: bool = Field(
        description=(
            "If `True`, the group is local to the TrueNAS server. If `False`, the group is provided by a directory "
            "service."
        ),
    )
    sid: str | None = Field(
        description=(
            "The Security Identifier (SID) of the user if the account an `smb` account. The SMB server uses this value "
            "to check share access and for other purposes."
        ),
    )
    roles: list[str] = Field(
        description=(
            "List of roles assigned to this groups. Roles control administrative access to TrueNAS through the web UI "
            "and API. You can change group roles by using `privilege.create`, `privilege.update`, and "
            "`privilege.delete`."
        ),
    )
    users: list[int] = Field(
        default=[],
        description=(
            "A list a API user identifiers for local users who are members of this group. These IDs match the `id` "
            "field from `user.query`.\n"
            "\n"
            "NOTE: This field is empty for groups that come from directory services (`local` is `False`)."
        ),
    )
    immutable: bool = Field(
        description=(
            "This is a read-only field showing if the group entry can be changed. If `True`, the group is immutable and"
            " cannot be changed. If `False`, the group can be changed."
        ),
    )


class GroupCreate(GroupEntry):
    id: Excluded = excluded_field()
    builtin: Excluded = excluded_field()
    immutable: Excluded = excluded_field()
    group: Excluded = excluded_field()
    local: Excluded = excluded_field()
    sid: Excluded = excluded_field()
    roles: Excluded = excluded_field()

    gid: LocalUID | None = Field(
        default=None,
        description="If `null`, it is automatically filled with the next one available.",
    )
    name: GroupName


class GroupCreateArgs(BaseModel):
    group_create: GroupCreate = Field(description="Group configuration data for the new group.")


class GroupCreateResult(BaseModel):
    result: int = Field(description="The API identifier of the newly created group.")


class GroupUpdate(GroupCreate, metaclass=ForUpdateMetaclass):
    gid: Excluded = excluded_field()


class GroupUpdateArgs(BaseModel):
    id: int = Field(description="The API identifier of the group to update.")
    group_update: GroupUpdate = Field(description="Updated group configuration data.")


class GroupUpdateResult(BaseModel):
    result: int = Field(description="The API identifier of the updated group.")


class GroupDeleteOptions(BaseModel):
    delete_users: bool = Field(
        default=False,
        description="Deletes all users that have this group as their primary group.",
    )


class GroupDeleteArgs(BaseModel):
    id: int = Field(description="API identifier of the group to delete.")
    options: GroupDeleteOptions = Field(
        default=GroupDeleteOptions(),
        description="Options controlling group deletion behavior.",
    )


class GroupDeleteResult(BaseModel):
    result: int = Field(description="The API identifier of the deleted group.")


class GroupGetNextGidArgs(BaseModel):
    pass


class GroupGetNextGidResult(BaseModel):
    result: int = Field(description="The next available group ID number.")


@single_argument_args("get_group_obj")
class GroupGetGroupObjArgs(BaseModel):
    groupname: str | None = Field(default=None, description="Name of the group to look up or `null`.")
    gid: int | None = Field(default=None, description="Group ID to look up or `null`.")
    sid_info: bool = Field(default=False, description="Whether to include SID information in the response.")


@single_argument_result
class GroupGetGroupObjResult(BaseModel):
    gr_name: str = Field(description="Name of the group.")
    gr_gid: int = Field(description="Group ID of the group.")
    gr_mem: list[str] = Field(description="List of group names that are members of the group.")
    sid: str | None = Field(
        default=None,
        description="Optional SID value for the account that is present if `sid_info` is specified in payload.",
    )
    source: Literal['LOCAL', 'ACTIVEDIRECTORY', 'LDAP'] = Field(
        description=(
            "The name server switch module that provided the user. Options are:\n"
            "\n"
            "* FILES: Local user in passwd file of server.\n"
            "* WINBIND: User provided by winbindd.\n"
            "* SSS: User provided by SSSD."
        ),
    )
    local: bool = Field(description="This group is local to the NAS or provided by a directory service.")


class GroupHasPasswordEnabledUserArgs(BaseModel):
    gids: list[int] = Field(description="Array of group IDs to check for password-enabled users.")
    exclude_user_ids: list[int] = Field(default=[], description="Array of user IDs to exclude from the check.")


class GroupHasPasswordEnabledUserResult(BaseModel):
    result: bool = Field(description="Returns `true` if any of the groups contain password-enabled users.")
