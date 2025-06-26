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
    """ This is the API identifier for the user. Use this ID for `user.update` and `user.delete` API calls. This ID
    also appears in the `users` array for each group entry in `group.query` results.

    NOTE: For users from a directory service, the `id` is calculated by adding 100000000 to the `uid`. This ensures
    consistent API results. You cannot change directory service accounts through TrueNAS. """
    uid: int
    """ A non-negative integer used to identify a system user. TrueNAS uses this value for permission
    checks and many other system purposes. """
    username: LocalUsername | RemoteUsername
    """ A string used to identify a user. Local accounts must use characters from the POSIX portable filename character
    set. """
    unixhash: Secret[str | None]
    """ Hashed password for local accounts. This value is `None` for accounts provided by directory services. """
    smbhash: Secret[str | None]
    """ NT hash of the local account password for `smb` users. This value is `None` for accounts provided by directory
    services or non-SMB accounts. """
    home: NonEmptyString = DEFAULT_HOME_PATH
    """ The local file system path for the user account's home directory.
    Typically, this is required only if the account has shell access (local or SSH) to TrueNAS.
    This is not required for accounts used only for SMB share access. """
    shell: NonEmptyString = "/usr/bin/zsh"
    """Available choices can be retrieved with `user.shell_choices`."""
    full_name: str
    """ Comment field to provide additional information about the user account. Typically, this is
    the full name of the user or a short description of a service account. There are no character set restrictions
    for this field. This field is for information only. """
    builtin: bool
    """ If `True`, the user account is an internal system account for the TrueNAS server. Typically, one should
    create dedicated user accounts for access to the TrueNAS server webui and shares. """
    smb: bool = True
    """ The user account may be used to access SMB shares. If set to `True` then TrueNAS stores an NT hash of the
    user account's password for local accounts. This feature is unavailable for local accounts when General Purpose OS
    STIG compatibility mode is enabled. If set to `True` the user is automatically added to the `builtin_users`
    group."""
    userns_idmap: Literal['DIRECT', None] | ContainerXID = None
    """
    Specifies the subuid mapping for this user. If DIRECT then the UID will be \
    directly mapped to all containers. Alternatively, the target UID may be \
    explicitly specified. If None, then the UID will not be mapped.

    NOTE: This field will be ignored for users that have been assigned
    TrueNAS roles.
    """
    group: dict
    """ The primary group of the user account. """
    groups: list[int] = Field(default_factory=list)
    """ List of additional groups to which the user belongs. NOTE: groups are identified by their group entry `id`,
    not their Unix group ID (`gid`). """
    password_disabled: bool = False
    """ If set to `True` password authentication for the user account is disabled.

    NOTE: users with password authentication disabled may still authenticate to the TrueNAS server by other methods,
    such as SSH key-based authentication.

    NOTE: password authentication is required for `smb` users.
    """
    ssh_password_enabled: bool = False
    """ Allow the user to authenticate to the TrueNAS SSH server using a password.

    WARNING: the established best practice is to use only key-based authentication for SSH servers. """
    sshpubkey: LongString | None = None
    """  SSH public keys corresponding to private keys that authenticate this user to the TrueNAS SSH server. """
    locked: bool = False
    """ If set to `True` the account is locked. The account cannot be used to authenticate to the TrueNAS server. """
    sudo_commands: list[NonEmptyString] = Field(default_factory=list)
    """ A list of commands the user may execute with elevated privileges. User is prompted for password
    when executing any command from the list. """
    sudo_commands_nopasswd: list[NonEmptyString] = Field(default_factory=list)
    """ A list of commands the user may execute with elevated privileges. User is *not* prompted for password
    when executing any command from the list. """
    email: EmailStr | None = None
    """ Email address of the user. If the user has the `FULL_ADMIN` role, they will receive email alerts and
    notifications. """
    local: bool
    """ If `True`, the account is local to the TrueNAS server. If `False`, the account is provided by a directory
    service. """
    immutable: bool
    """ If `True`, the account is system-provided and most fields related to it may not be changed. """
    twofactor_auth_configured: bool
    """ If `True, the account has been configured for two-factor authentication. Users are prompted for a
    second factor when authenticating to the TrueNAS web UI and API. They may also be prompted when signing
    in to the TrueNAS SSH server using a password (depending on global two-factor authentication settings). """
    sid: str | None
    """ The Security Identifier (SID) of the user if the account an `smb` account. The SMB server uses
    this value to check share access and for other purposes. """
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
    """ List of roles assigned to this user's groups. Roles control administrative access to TrueNAS through
    the web UI and API. """
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
    """ Comment field to provide additional information about the user account. Typically, this is
    the full name of the user or a short description of a service account. There are no character set restrictions
    for this field. This field is for information only. """
    group_create: bool = False
    """ If set to True, the TrueNAS server automatically creates a new local group as the user's primary group. """
    group: int | None = None
    """ The group entry `id` for the user's primary group. This is not the same as the Unix group `gid` value.
    This is required if `group_create` is `false`. """
    home_create: bool = False
    """ Create a new home directory for the user in the specified `home` path. """
    home_mode: str = "700"
    """ Filesystem permission to set on the user's home directory. """
    password: Secret[NonEmptyString | None] = None
    """ The password for the user account. This is required if `random_password` is not set. """
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
