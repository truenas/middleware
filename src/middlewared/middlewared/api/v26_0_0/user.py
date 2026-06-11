from typing import Literal

from datetime import datetime
from pydantic import Field, Secret

from middlewared.api.base import (
    BaseModel,
    ContainerXID,
    Excluded,
    EmailString,
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
    id: int = Field(
        description=(
            "This is the API identifier for the user. Use this ID for `user.update` and `user.delete` API calls. This "
            "ID also appears in the `users` array for each group entry in `group.query` results.\n"
            "\n"
            "NOTE: For users from a directory service, the `id` is calculated by adding 100000000 to the `uid`. This "
            "ensures consistent API results. You cannot change directory service accounts through TrueNAS."
        ),
    )
    uid: int = Field(
        description=(
            "A non-negative integer used to identify a system user. TrueNAS uses this value for permission checks and "
            "many other system purposes."
        ),
    )
    username: LocalUsername | RemoteUsername = Field(
        description=(
            "A string used to identify a user. Local accounts must use characters from the POSIX portable filename "
            "character set."
        ),
    )
    unixhash: Secret[str | None] = Field(
        description=(
            "Hashed password for local accounts. This value is `null` for accounts provided by directory services."
        ),
    )
    smbhash: Secret[str | None] = Field(
        description=(
            "NT hash of the local account password for `smb` users. This value is `null` for accounts provided by "
            "directory services or non-SMB accounts."
        ),
    )
    home: NonEmptyString = Field(
        default=DEFAULT_HOME_PATH,
        description=(
            "The local file system path for the user account's home directory. Typically, this is required only if the "
            "account has shell access (local or SSH) to TrueNAS. This is not required for accounts used only for SMB "
            "share access."
        ),
    )
    shell: NonEmptyString = Field(
        default="/usr/bin/zsh",
        description="Available choices can be retrieved with `user.shell_choices`.",
    )
    full_name: str = Field(
        description=(
            "Comment field to provide additional information about the user account. Typically, this is the full name "
            "of the user or a short description of a service account. There are no character set restrictions for this "
            "field. This field is for information only."
        ),
    )
    builtin: bool = Field(
        description=(
            "If `true`, the user account is an internal system account for the TrueNAS server. Typically, one should "
            "create dedicated user accounts for access to the TrueNAS server webui and shares."
        ),
    )
    smb: bool = Field(
        default=True,
        description=(
            "The user account may be used to access SMB shares. If set to `true` then TrueNAS stores an NT hash of the "
            "user account's password for local accounts. This feature is unavailable for local accounts when General "
            "Purpose OS STIG compatibility mode is enabled. If set to `true` the user is automatically added to the "
            "`builtin_users` group."
        ),
    )
    webshare: bool = Field(
        default=False,
        description=(
            "The user account may be used to access WebShare shares. If set to `true` the user is automatically added "
            "to the `webshare` group."
        ),
    )
    userns_idmap: Literal['DIRECT', None] | ContainerXID = Field(
        default=None,
        description=(
            "Specifies the subuid mapping for this user. If DIRECT then the UID will be directly mapped to all "
            "containers. Alternatively, the target UID may be explicitly specified. If `null`, then the UID will not be"
            " mapped.\n"
            "\n"
            "NOTE: This field will be ignored for users that have been assigned TrueNAS roles."
        ),
    )
    group: dict = Field(description="The primary group of the user account.")
    groups: list[int] = Field(
        default_factory=list,
        description=(
            "Array of additional groups to which the user belongs. NOTE: Groups are identified by their group entry "
            "`id`, not their Unix group ID (`gid`)."
        ),
    )
    password_disabled: bool = Field(
        default=False,
        description=(
            "If set to `true` password authentication for the user account is disabled.\n"
            "\n"
            "NOTE: Users with password authentication disabled may still authenticate to the TrueNAS server by other "
            "methods, such as SSH key-based authentication.\n"
            "\n"
            "NOTE: Password authentication is required for `smb` users."
        ),
    )
    ssh_password_enabled: bool = Field(
        default=False,
        description=(
            "Allow the user to authenticate to the TrueNAS SSH server using a password.\n"
            "\n"
            "WARNING: The established best practice is to use only key-based authentication for SSH servers."
        ),
    )
    sshpubkey: LongString | None = Field(
        default=None,
        description=(
            "SSH public keys corresponding to private keys that authenticate this user to the TrueNAS SSH server."
        ),
    )
    locked: bool = Field(
        default=False,
        description=(
            "If set to `true` the account is locked. The account cannot be used to authenticate to the TrueNAS server."
        ),
    )
    sudo_commands: list[NonEmptyString] = Field(
        default_factory=list,
        description=(
            "An array of commands the user may execute with elevated privileges. User is prompted for password when "
            "executing any command from the array."
        ),
    )
    sudo_commands_nopasswd: list[NonEmptyString] = Field(
        default_factory=list,
        description=(
            "An array of commands the user may execute with elevated privileges. User is *not* prompted for password "
            "when executing any command from the array."
        ),
    )
    email: NonEmptyString | None = Field(
        default=None,
        description=(
            "Email address of the user. If the user has the `FULL_ADMIN` role, they will receive email alerts and "
            "notifications."
        ),
    )
    local: bool = Field(
        description=(
            "If `true`, the account is local to the TrueNAS server. If `false`, the account is provided by a directory "
            "service."
        ),
    )
    immutable: bool = Field(
        description="If `true`, the account is system-provided and most fields related to it may not be changed.",
    )
    twofactor_auth_configured: bool = Field(
        description=(
            "If `true`, the account has been configured for two-factor authentication. Users are prompted for a second "
            "factor when authenticating to the TrueNAS web UI and API. They may also be prompted when signing in to the"
            " TrueNAS SSH server using a password (depending on global two-factor authentication settings)."
        ),
    )
    sid: str | None = Field(
        description=(
            "The Security Identifier (SID) of the user if the account an `smb` account. The SMB server uses this value "
            "to check share access and for other purposes."
        ),
    )
    last_password_change: datetime | None = Field(
        description="The date of the last password change for local user accounts.",
    )
    password_age: int | None = Field(description="The age in days of the password for local user accounts.")
    password_history: Secret[list | None] = Field(
        description=(
            "This contains hashes of the ten most recent passwords used by local user accounts, and is for enforcing "
            "password history requirements as defined in system.security."
        ),
    )
    password_change_required: bool = Field(
        description="Password change for local user account is required on next login.",
    )
    roles: list[str] = Field(
        description=(
            "Array of roles assigned to this user's groups. Roles control administrative access to TrueNAS through the "
            "web UI and API."
        ),
    )
    api_keys: list[int] = Field(
        description="Array of API key IDs associated with this user account for programmatic access.",
    )


class UserCreateUpdateResult(UserEntry):
    password: NonEmptyString | None = Field(
        description=(
            "Password if it was specified in create or update payload. If random_password was specified then this will "
            "be a 20 character random string."
        ),
    )


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

    uid: LocalUID | None = Field(
        default=None,
        description="UNIX UID. If not provided, it is automatically filled with the next one available.",
    )
    username: LocalUsername = Field(
        description=(
            "String used to uniquely identify the user on the server. In order to be portable across systems, local "
            "user names must be composed of characters from the POSIX portable filename character set (IEEE Std "
            "1003.1-2024 section 3.265). This means alphanumeric characters, hyphens, underscores, and periods. "
            "Usernames also may not begin with a hyphen or a period."
        ),
    )
    full_name: NonEmptyString = Field(
        description=(
            "Comment field to provide additional information about the user account. Typically, this is the full name "
            "of the user or a short description of a service account. There are no character set restrictions for this "
            "field. This field is for information only."
        ),
    )
    email: EmailString | None = None
    group_create: bool = Field(
        default=False,
        description=(
            "If set to `true`, the TrueNAS server automatically creates a new local group as the user's primary group."
        ),
    )
    group: int | None = Field(
        default=None,
        description=(
            "The group entry `id` for the user's primary group. This is not the same as the Unix group `gid` value. "
            "This is required if `group_create` is `false`."
        ),
    )
    home_create: bool = Field(
        default=False,
        description="Create a new home directory for the user in the specified `home` path.",
    )
    home_mode: str = Field(default="700", description="Filesystem permission to set on the user's home directory.")
    password: Secret[NonEmptyString | None] = Field(
        default=None,
        description="The password for the user account. This is required if `random_password` is not set.",
    )
    random_password: bool = Field(default=False, description="Generate a random 20 character password for the user.")


class UserGetUserObj(BaseModel):
    pw_name: str = Field(description="Name of the user.")
    pw_gecos: str = Field(description="Full username or comment field.")
    pw_dir: str = Field(description="User home directory.")
    pw_shell: str = Field(description="User command line interpreter.")
    pw_uid: int = Field(description="Numerical user ID of the user.")
    pw_gid: int = Field(description="Numerical group id for the user's primary group.")
    grouplist: list[int] | None = Field(
        description=(
            "Optional array of group IDs for groups of which this account is a member. If `get_groups` is not "
            "specified, this value will be `null`."
        ),
    )
    sid: str | None = Field(
        description="Optional SID value for the account that is present if `sid_info` is specified in payload.",
    )
    source: Literal['LOCAL', 'ACTIVEDIRECTORY', 'LDAP'] = Field(description="The source for the user account.")
    local: bool = Field(description="The account is local to TrueNAS or provided by a directory service.")


class UserUpdate(UserCreate, metaclass=ForUpdateMetaclass):
    uid: Excluded = excluded_field()
    group_create: Excluded = excluded_field()


class UserCreateArgs(BaseModel):
    user_create: UserCreate = Field(description="Configuration for creating a new user account.")


class UserCreateResult(BaseModel):
    result: UserCreateUpdateResult = Field(description="The newly created user account with password information.")


class UserUpdateArgs(BaseModel):
    id: int = Field(description="ID of the user account to update.")
    user_update: UserUpdate = Field(description="Updated configuration for the user account.")


class UserUpdateResult(BaseModel):
    result: UserCreateUpdateResult = Field(description="The updated user account with password information.")


class UserDeleteOptions(BaseModel):
    delete_group: bool = Field(
        default=True,
        description="Delete the user primary group if it is not being used by any other user.",
    )


class UserDeleteArgs(BaseModel):
    id: int = Field(description="ID of the user account to delete.")
    options: UserDeleteOptions = Field(
        default_factory=UserDeleteOptions,
        description="Options controlling the user deletion process.",
    )


class UserDeleteResult(BaseModel):
    result: int = Field(description="ID of the deleted user account.")


class UserShellChoicesArgs(BaseModel):
    group_ids: list[int] = Field(
        default=[],
        description="Array of group IDs to filter shell choices. Empty array returns all shells.",
    )


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
    ],
        description="Object of available shell paths and their descriptive names.")


@single_argument_args("get_user_obj")
class UserGetUserObjArgs(BaseModel):
    username: str | None = Field(
        default=None,
        description="Username to lookup. Either `username` or `uid` must be specified.",
    )
    uid: int | None = Field(
        default=None,
        description="User ID to lookup. Either `username` or `uid` must be specified.",
    )
    get_groups: bool = Field(default=False, description="Retrieve group list for the specified user.")
    sid_info: bool = Field(default=False, description="Retrieve SID and domain information for the user.")


class UserGetUserObjResult(BaseModel):
    result: UserGetUserObj = Field(description="User account information in Unix passwd format.")


class UserGetNextUidArgs(BaseModel):
    pass


class UserGetNextUidResult(BaseModel):
    result: int = Field(description="Next available UID for creating a new local user account.")


class UserHasLocalAdministratorSetUpArgs(BaseModel):
    pass


class UserHasLocalAdministratorSetUpResult(BaseModel):
    result: bool = Field(description="Whether a local administrator account has been configured on this system.")


class UserSetupLocalAdministratorEC2Options(BaseModel):
    instance_id: NonEmptyString = Field(description="EC2 instance identifier for cloud-specific administrator setup.")


class UserSetupLocalAdministratorOptions(BaseModel):
    ec2: UserSetupLocalAdministratorEC2Options | None = Field(
        default=None,
        description="Cloud platform-specific options for administrator setup. `null` for standard setup.",
    )


class UserSetupLocalAdministratorArgs(BaseModel):
    username: Literal['root', 'truenas_admin'] = Field(description="Administrator username to configure.")
    password: Secret[str] = Field(description="Password for the administrator account.")
    options: UserSetupLocalAdministratorOptions = Field(
        default_factory=UserSetupLocalAdministratorOptions,
        description="Additional options for cloud or specialized administrator setup.",
    )


class UserSetupLocalAdministratorResult(BaseModel):
    result: None = Field(description="Returns `null` on successful administrator account setup.")


@single_argument_args("set_password_data")
class UserSetPasswordArgs(BaseModel):
    username: str = Field(description="Username of the account to change password for.")
    old_password: Secret[str | None] = Field(
        default=None,
        description="Current password for verification. `null` if changing password as administrator.",
    )
    new_password: Secret[NonEmptyString] = Field(description="New password to set for the user account.")


class UserSetPasswordResult(BaseModel):
    result: None = Field(description="Returns `null` on successful password change.")


class UserTwofactorConfigEntry(BaseModel):
    provisioning_uri: str | None = Field(
        description=(
            "QR code URI for setting up two-factor authentication in authenticator apps. `null` if not available."
        ),
    )
    secret_configured: bool = Field(
        description="Whether a two-factor authentication secret has been configured for this user.",
    )
    interval: int = Field(description="Time interval in seconds for OTP validity period.")
    otp_digits: int = Field(description="Number of digits in the generated one-time password codes.")


class UserUnset2faSecretArgs(BaseModel):
    username: str = Field(description="Username to disable two-factor authentication for.")


class UserUnset2faSecretResult(BaseModel):
    result: None = Field(description="Returns `null` on successful two-factor authentication removal.")


class TwofactorOptions(BaseModel, metaclass=ForUpdateMetaclass):
    otp_digits: int = Field(ge=6, le=8, description="Represents number of allowed digits in the OTP.")
    interval: int = Field(
        ge=5,
        description="Time duration in seconds specifying OTP expiration time from its creation time.",
    )


class UserRenew2faSecretArgs(BaseModel):
    username: str = Field(description="Username to renew two-factor authentication secret for.")
    twofactor_options: TwofactorOptions = Field(
        description="Configuration options for the new two-factor authentication setup.",
    )


@single_argument_result
class UserRenew2faSecretResult(UserEntry):
    twofactor_config: UserTwofactorConfigEntry = Field(
        description="New two-factor authentication configuration with provisioning details.",
    )
