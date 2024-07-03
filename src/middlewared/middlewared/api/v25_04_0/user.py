from annotated_types import Ge, Le
from pydantic import EmailStr
from typing_extensions import Annotated

from middlewared.api.base import (BaseModel, Excluded, excluded_field, ForUpdateMetaclass, LocalUsername, LocalUID,
                                  LongString, NonEmptyString, Private, single_argument_result)
from middlewared.plugins.account_.constants import DEFAULT_HOME_PATH

__all__ = ["UserEntry", "UserCreateArgs", "UserCreateResult", "UserUpdateArgs", "UserUpdateResult",
           "UserRenew2faSecretArgs", "UserRenew2faSecretResult"]


class UserEntry(BaseModel):
    id: int
    uid: int
    username: LocalUsername
    unixhash: Private[str]
    smbhash: Private[str]
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
    nt_name: str | None
    sid: str | None
    roles: list[str]


class UserCreate(UserEntry):
    id: Excluded = excluded_field()
    unixhash: Excluded = excluded_field()
    smbhash: Excluded = excluded_field()
    builtin: Excluded = excluded_field()
    id_type_both: Excluded = excluded_field()
    local: Excluded = excluded_field()
    immutable: Excluded = excluded_field()
    twofactor_auth_configured: Excluded = excluded_field()
    nt_name: Excluded = excluded_field()
    sid: Excluded = excluded_field()
    roles: Excluded = excluded_field()

    uid: LocalUID | None = None
    "UNIX UID. If not provided, it is automatically filled with the next one available."
    full_name: NonEmptyString

    group_create: bool = False
    group: int | None = None
    "Required if `group_create` is `false`."
    home_create: bool = False
    home_mode: str = "700"
    password: Private[str | None] = None


class UserUpdate(UserCreate, metaclass=ForUpdateMetaclass):
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


class TwofactorOptions(BaseModel, metaclass=ForUpdateMetaclass):
    otp_digits: Annotated[int, Ge(6), Le(8)]
    "Represents number of allowed digits in the OTP"
    interval: Annotated[int, Ge(5)]
    "Time duration in seconds specifying OTP expiration time from its creation time"


class UserRenew2faSecretArgs(BaseModel):
    username: str
    twofactor_options: TwofactorOptions


UserRenew2faSecretResult = single_argument_result(UserEntry)
