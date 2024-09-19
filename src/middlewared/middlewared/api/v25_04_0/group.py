from typing import Literal

from pydantic import Field

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LocalUID, NonEmptyString,
                                  single_argument_args, single_argument_result)

__all__ = ["GroupEntry",
           "GroupCreateArgs", "GroupCreateResult",
           "GroupUpdateArgs", "GroupUpdateResult",
           "GroupDeleteArgs", "GroupDeleteResult",
           "GroupGetNextGidArgs", "GroupGetNextGidResult",
           "GroupGetGroupObjArgs", "GroupGetGroupObjResult",
           "GroupHasPasswordEnabledUserArgs", "GroupHasPasswordEnabledUserResult"]


class GroupEntry(BaseModel):
    id: int
    gid: int
    name: NonEmptyString
    builtin: bool
    sudo_commands: list[NonEmptyString] = []
    sudo_commands_nopasswd: list[NonEmptyString] = []
    smb: bool = True
    "Specifies whether the group should be mapped into an NT group."
    group: NonEmptyString
    id_type_both: bool
    local: bool
    sid: str | None
    roles: list[str]
    users: list[int] = []
    "A list of user ids (`id` attribute from `user.query`)."


class GroupCreate(GroupEntry):
    id: Excluded = excluded_field()
    builtin: Excluded = excluded_field()
    group: Excluded = excluded_field()
    id_type_both: Excluded = excluded_field()
    local: Excluded = excluded_field()
    sid: Excluded = excluded_field()
    roles: Excluded = excluded_field()

    gid: LocalUID | None = None
    "If `null`, it is automatically filled with the next one available."
    allow_duplicate_gid: bool = False
    "Allows distinct group names to share the same gid."


class GroupCreateArgs(BaseModel):
    group_create: GroupCreate


class GroupCreateResult(BaseModel):
    result: int


class GroupUpdate(GroupCreate, metaclass=ForUpdateMetaclass):
    pass


class GroupUpdateArgs(BaseModel):
    id: int
    group_update: GroupUpdate


class GroupUpdateResult(BaseModel):
    result: int


class GroupDeleteOptions(BaseModel):
    delete_users: bool = False
    "Deletes all users that have this group as their primary group."


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
    "name of the group"
    gr_gid: int
    "group id of the group"
    gr_mem: list[int]
    "list of gids that are members of the group"
    sid: str | None = None
    "optional SID value for the account that is present if `sid_info` is specified in payload."
    source: Literal['LOCAL', 'ACTIVEDIRECTORY', 'LDAP']
    """
    the name server switch module that provided the user. Options are:
        FILES - local user in passwd file of server,
        WINBIND - user provided by winbindd,
        SSS - user provided by SSSD.
    """
    local: bool
    "boolean indicating whether this group is local to the NAS or provided by a directory service."


class GroupHasPasswordEnabledUserArgs(BaseModel):
    gids: list[int]
    exclude_user_ids: list[int] = []


class GroupHasPasswordEnabledUserResult(BaseModel):
    result: bool
