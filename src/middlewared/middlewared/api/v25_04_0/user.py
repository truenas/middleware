from typing import Literal

from annotated_types import Ge, Le
from pydantic import EmailStr, Field, Secret
from typing_extensions import Annotated

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LocalUsername, RemoteUsername,
                                  LocalUID, LongString, NonEmptyString, single_argument_args, single_argument_result)

__all__ = ["UserEntry",
           "UserCreateArgs", "UserCreateResult",
           "UserUpdateArgs", "UserUpdateResult",
           "UserDeleteArgs", "UserDeleteResult",
           "UserShellChoicesArgs", "UserShellChoicesResult",
           "UserGetUserObjArgs", "UserGetUserObjResult",
           "UserGetNextUidArgs", "UserGetNextUidResult",
           "UserHasLocalAdministratorSetUpArgs", "UserHasLocalAdministratorSetUpResult",
           "UserSetupLocalAdministratorArgs", "UserSetupLocalAdministratorResult",
           "UserSetPasswordArgs", "UserSetPasswordResult",
           "UserProvisioningUriArgs", "UserProvisioningUriResult",
           "UserTwofactorConfigArgs", "UserTwofactorConfigResult",
           "UserVerifyTwofactorTokenArgs", "UserVerifyTwofactorTokenResult",
           "UserUnset2faSecretArgs", "UserUnset2faSecretResult",
           "UserRenew2faSecretArgs", "UserRenew2faSecretResult"]


DEFAULT_HOME_PATH = "/var/empty"


class UserEntry(BaseModel):
    id: int
    uid: int
    username: LocalUsername | RemoteUsername
    unixhash: Secret[str | None]
    smbhash: Secret[str | None]
    home: NonEmptyString = DEFAULT_HOME_PATH
    shell: NonEmptyString = "/usr/bin/zsh"
    "Available choices can be retrieved with `user.shell_choices`."
    full_name: str
    builtin: bool
    smb: bool = True
    group: dict
    groups: list[int] = []
    """Specifies whether the user should be allowed access to SMB shares. User will also automatically be added to
    the `builtin_users` group."""
    password_disabled: bool = False
    ssh_password_enabled: bool = False
    "Required if `password_disabled` is false."
    sshpubkey: LongString | None = None
    locked: bool = False
    sudo_commands: list[NonEmptyString] = []
    sudo_commands_nopasswd: list[NonEmptyString] = []
    email: EmailStr | None = None
    id_type_both: bool
    local: bool
    immutable: bool
    twofactor_auth_configured: bool
    sid: str | None
    roles: list[str]
    api_keys: list[int]


class UserCreate(UserEntry):
    id: Excluded = excluded_field()
    unixhash: Excluded = excluded_field()
    smbhash: Excluded = excluded_field()
    builtin: Excluded = excluded_field()
    id_type_both: Excluded = excluded_field()
    local: Excluded = excluded_field()
    immutable: Excluded = excluded_field()
    twofactor_auth_configured: Excluded = excluded_field()
    sid: Excluded = excluded_field()
    roles: Excluded = excluded_field()
    api_keys: Excluded = excluded_field()

    uid: LocalUID | None = None
    "UNIX UID. If not provided, it is automatically filled with the next one available."
    full_name: NonEmptyString

    group_create: bool = False
    group: int | None = None
    "Required if `group_create` is `false`."
    home_create: bool = False
    home_mode: str = "700"
    password: Secret[str | None] = None


class UserUpdate(UserCreate, metaclass=ForUpdateMetaclass):
    uid: Excluded = excluded_field()
    group_create: Excluded = excluded_field()


class UserCreateArgs(BaseModel):
    user_create: UserCreate


class UserCreateResult(BaseModel):
    result: int


class UserUpdateArgs(BaseModel):
    id: int
    user_update: UserUpdate


class UserUpdateResult(BaseModel):
    result: int


class UserDeleteOptions(BaseModel):
    delete_group: bool = True
    "Deletes the user primary group if it is not being used by any other user."


class UserDeleteArgs(BaseModel):
    id: int
    options: UserDeleteOptions = Field(default=UserDeleteOptions())


class UserDeleteResult(BaseModel):
    result: int


class UserShellChoicesArgs(BaseModel):
    group_ids: list[int] = []


class UserShellChoicesResult(BaseModel):
    result: dict = Field(examples=[
        {
            '/usr/bin/bash': 'bash',
            '/usr/bin/rbash': 'rbash',
            '/usr/bin/dash': 'dash',
            '/usr/bin/sh': 'sh',
            '/usr/bin/zsh': 'zsh',
            '/usr/bin/tmux': 'tmux',
            '/usr/sbin/nologin': 'nologin'
        },
    ])


@single_argument_args("get_user_obj")
class UserGetUserObjArgs(BaseModel):
    username: str | None = None
    uid: int | None = None
    get_groups: bool = False
    "retrieve group list for the specified user."
    sid_info: bool = False
    "retrieve SID and domain information for the user."


@single_argument_result
class UserGetUserObjResult(BaseModel):
    pw_name: str
    "name of the user"
    pw_gecos: str
    "full username or comment field"
    pw_dir: str
    "user home directory"
    pw_shell: str
    "user command line interpreter"
    pw_uid: int
    "numerical user id of the user"
    pw_gid: int
    "numerical group id for the user's primary group"
    grouplist: list[int] | None
    """
    optional list of group ids for groups of which this account is a member. If `get_groups` is not specified,
    this value will be null.
    """
    sid: str | None
    "optional SID value for the account that is present if `sid_info` is specified in payload."
    source: Literal['LOCAL', 'ACTIVEDIRECTORY', 'LDAP']
    "the source for the user account."
    local: bool
    "boolean value indicating whether the account is local to TrueNAS or provided by a directory service."


class UserGetNextUidArgs(BaseModel):
    pass


class UserGetNextUidResult(BaseModel):
    result: int


class UserHasLocalAdministratorSetUpArgs(BaseModel):
    pass


class UserHasLocalAdministratorSetUpResult(BaseModel):
    result: bool


class UserSetupLocalAdministratorEC2Options(BaseModel):
    instance_id: NonEmptyString


class UserSetupLocalAdministratorOptions(BaseModel):
    ec2: UserSetupLocalAdministratorEC2Options | None = None


class UserSetupLocalAdministratorArgs(BaseModel):
    username: Literal['root', 'truenas_admin']
    password: Secret[str]
    options: UserSetupLocalAdministratorOptions = Field(default=UserSetupLocalAdministratorOptions())


class UserSetupLocalAdministratorResult(BaseModel):
    result: None


@single_argument_args("set_password_data")
class UserSetPasswordArgs(BaseModel):
    username: str
    old_password: Secret[str | None] = None
    new_password: Secret[NonEmptyString]


class UserSetPasswordResult(BaseModel):
    result: None


class UserProvisioningUriArgs(BaseModel):
    username: str


class UserProvisioningUriResult(BaseModel):
    result: str


class UserTwofactorConfigArgs(BaseModel):
    username: str


@single_argument_result
class UserTwofactorConfigResult(BaseModel):
    provisioning_uri: str | None
    secret_configured: bool
    interval: int
    otp_digits: int


class UserVerifyTwofactorTokenArgs(BaseModel):
    username: str
    token: Secret[str | None] = None


class UserVerifyTwofactorTokenResult(BaseModel):
    result: bool


class UserUnset2faSecretArgs(BaseModel):
    username: str


class UserUnset2faSecretResult(BaseModel):
    result: None


class TwofactorOptions(BaseModel, metaclass=ForUpdateMetaclass):
    otp_digits: Annotated[int, Ge(6), Le(8)]
    "Represents number of allowed digits in the OTP"
    interval: Annotated[int, Ge(5)]
    "Time duration in seconds specifying OTP expiration time from its creation time"


class UserRenew2faSecretArgs(BaseModel):
    username: str
    twofactor_options: TwofactorOptions


UserRenew2faSecretResult = single_argument_result(UserEntry, "UserRenew2faSecretResult")
