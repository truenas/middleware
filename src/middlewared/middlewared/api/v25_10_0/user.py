from typing import Literal

from datetime import datetime
from pydantic import EmailStr, Field, Secret

from middlewared.api.base import (
    BaseModel,
    ContainerXID,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    LocalUsername,
    RemoteUsername,
    LocalUID,
    LongString,
    NonEmptyString,
    single_argument_args,
    single_argument_result
)
from middlewared.plugins.account_.constants import DEFAULT_HOME_PATH

__all__ = ["UserEntry",
           "UserCreateArgs", "UserCreateResult",
           "UserUpdateArgs", "UserUpdateResult",
           "UserDeleteArgs", "UserDeleteResult",
           "UserShellChoicesArgs", "UserShellChoicesResult",
           "UserGetUserObjArgs", "UserGetUserObjResult", "UserGetUserObj",
           "UserGetNextUidArgs", "UserGetNextUidResult",
           "UserHasLocalAdministratorSetUpArgs", "UserHasLocalAdministratorSetUpResult",
           "UserSetupLocalAdministratorArgs", "UserSetupLocalAdministratorResult",
           "UserSetPasswordArgs", "UserSetPasswordResult",
           "UserTwofactorConfigEntry",
           "UserUnset2faSecretArgs", "UserUnset2faSecretResult",
           "UserRenew2faSecretArgs", "UserRenew2faSecretResult"]


class UserEntry(BaseModel):
    id: int
    uid: int
    username: LocalUsername | RemoteUsername
    unixhash: Secret[str | None]
    smbhash: Secret[str | None]
    home: NonEmptyString = DEFAULT_HOME_PATH
    shell: NonEmptyString = "/usr/bin/zsh"
    """Available choices can be retrieved with `user.shell_choices`."""
    full_name: str
    builtin: bool
    smb: bool = True
    userns_idmap: Literal['DIRECT', None] | ContainerXID = None
    """
    Specifies the subuid mapping for this user. If DIRECT then the UID will be \
    directly mapped to all containers. Alternatively, the target UID may be \
    explicitly specified. If None, then the UID will not be mapped.

    NOTE: This field will be ignored for users that have been assigned
    TrueNAS roles.
    """
    group: dict
    groups: list[int] = Field(default_factory=list)
    """Specifies whether the user should be allowed access to SMB shares. User will also automatically be added to \
    the `builtin_users` group."""
    password_disabled: bool = False
    ssh_password_enabled: bool = False
    """Required if `password_disabled` is false."""
    sshpubkey: LongString | None = None
    locked: bool = False
    sudo_commands: list[NonEmptyString] = Field(default_factory=list)
    sudo_commands_nopasswd: list[NonEmptyString] = Field(default_factory=list)
    email: EmailStr | None = None
    id_type_both: bool
    local: bool
    immutable: bool
    twofactor_auth_configured: bool
    sid: str | None
    last_password_change: datetime | None
    """The date of the last password change for local user accounts."""
    password_age: int | None
    """The age in days of the password for local user accounts."""
    password_history: Secret[list | None]
    """
    This contains hashes of the ten most recent passwords used by local user accounts, and is \
    for enforcing password history requirements as defined in system.security.
    """
    password_change_required: bool
    """Password change for local user account is required on next login."""
    roles: list[str]
    api_keys: list[int]


class UserCreateUpdateResult(UserEntry):
    password: NonEmptyString | None
    """Password if it was specified in create or update payload. If random_password \
    was specified then this will be a 20 character random string."""


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
    last_password_change: Excluded = excluded_field()
    password_age: Excluded = excluded_field()
    password_history: Excluded = excluded_field()
    password_change_required: Excluded = excluded_field()
    roles: Excluded = excluded_field()
    api_keys: Excluded = excluded_field()

    uid: LocalUID | None = None
    """UNIX UID. If not provided, it is automatically filled with the next one available."""
    username: LocalUsername
    """
    String used to uniquely identify the user on the server. In order to be portable across \
    systems, local user names must be composed of characters from the POSIX portable filename \
    character set (IEEE Std 1003.1-2024 section 3.265). This means alphanumeric characters, \
    hyphens, underscores, and periods. Usernames also may not begin with a hyphen or a period.
    """
    full_name: NonEmptyString

    group_create: bool = False
    group: int | None = None
    """Required if `group_create` is `false`."""
    home_create: bool = False
    home_mode: str = "700"
    password: Secret[NonEmptyString | None] = None
    random_password: bool = False
    """Generate a random 20 character password for the user."""


class UserGetUserObj(BaseModel):
    pw_name: str
    """Name of the user."""
    pw_gecos: str
    """Full username or comment field."""
    pw_dir: str
    """User home directory."""
    pw_shell: str
    """User command line interpreter."""
    pw_uid: int
    """Numerical user ID of the user."""
    pw_gid: int
    """Numerical group id for the user's primary group."""
    grouplist: list[int] | None
    """
    Optional list of group IDs for groups of which this account is a member. If `get_groups` is not specified, \
    this value will be null.
    """
    sid: str | None
    """Optional SID value for the account that is present if `sid_info` is specified in payload."""
    source: Literal['LOCAL', 'ACTIVEDIRECTORY', 'LDAP']
    """The source for the user account."""
    local: bool
    """The account is local to TrueNAS or provided by a directory service."""


class UserUpdate(UserCreate, metaclass=ForUpdateMetaclass):
    uid: Excluded = excluded_field()
    group_create: Excluded = excluded_field()


class UserCreateArgs(BaseModel):
    user_create: UserCreate


class UserCreateResult(BaseModel):
    result: UserCreateUpdateResult


class UserUpdateArgs(BaseModel):
    id: int
    user_update: UserUpdate


class UserUpdateResult(BaseModel):
    result: UserCreateUpdateResult


class UserDeleteOptions(BaseModel):
    delete_group: bool = True
    """Delete the user primary group if it is not being used by any other user."""


class UserDeleteArgs(BaseModel):
    id: int
    options: UserDeleteOptions = Field(default_factory=UserDeleteOptions)


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
    """Retrieve group list for the specified user."""
    sid_info: bool = False
    """Retrieve SID and domain information for the user."""


class UserGetUserObjResult(BaseModel):
    result: UserGetUserObj


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
    options: UserSetupLocalAdministratorOptions = Field(default_factory=UserSetupLocalAdministratorOptions)


class UserSetupLocalAdministratorResult(BaseModel):
    result: None


@single_argument_args("set_password_data")
class UserSetPasswordArgs(BaseModel):
    username: str
    old_password: Secret[str | None] = None
    new_password: Secret[NonEmptyString]


class UserSetPasswordResult(BaseModel):
    result: None


class UserTwofactorConfigEntry(BaseModel):
    provisioning_uri: str | None
    secret_configured: bool
    interval: int
    otp_digits: int


class UserUnset2faSecretArgs(BaseModel):
    username: str


class UserUnset2faSecretResult(BaseModel):
    result: None


class TwofactorOptions(BaseModel, metaclass=ForUpdateMetaclass):
    otp_digits: int = Field(ge=6, le=8)
    """Represents number of allowed digits in the OTP."""
    interval: int = Field(ge=5)
    """Time duration in seconds specifying OTP expiration time from its creation time."""


class UserRenew2faSecretArgs(BaseModel):
    username: str
    twofactor_options: TwofactorOptions


@single_argument_result
class UserRenew2faSecretResult(UserEntry):
    twofactor_config: UserTwofactorConfigEntry
