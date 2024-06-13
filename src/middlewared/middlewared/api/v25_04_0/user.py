from typing import List, Optional

from annotated_types import Ge, Le
from pydantic import EmailStr
from typing_extensions import Annotated

from middlewared.api.base import *

__all__ = ["UserEntry", "UserCreateArgs", "UserCreateResult", "UserUpdateArgs", "UserUpdateResult",
           "UserRenew2faSecretArgs", "UserRenew2faSecretResult"]


DEFAULT_HOME_PATH = "/var/empty"
TRUENAS_IDMAP_DEFAULT_LOW = 90000001


class UserEntry(BaseModel):
    id: int
    uid: int
    username: LocalUsername
    unixhash: Private[str]
    smbhash: Private[str]
    home: NonEmptyString = DEFAULT_HOME_PATH
    shell: NonEmptyString = "/usr/bin/zsh"
    "Available choices can be retrieved with `user.shell_choices`."
    full_name: NonEmptyString
    builtin: bool
    smb: bool = True
    group: dict
    groups: List[int] = []
    """Specifies whether the user should be allowed access to SMB shares. User will also automatically be added to
    the `builtin_users` group."""
    password_disabled: bool = False
    ssh_password_enabled: bool = False
    "Required if `password_disabled` is false."
    sshpubkey: Optional[LongString] = None
    locked: bool = False
    sudo_commands: List[NonEmptyString] = []
    sudo_commands_nopasswd: List[NonEmptyString] = []
    email: Optional[EmailStr] = None
    id_type_both: bool
    local: bool
    immutable: bool
    twofactor_auth_configured: bool
    nt_name: Optional[str]
    sid: Optional[str]
    roles: List[str]


class UserCreate(UserEntry):
    id: excluded() = excluded_field()
    unixhash: excluded() = excluded_field()
    smbhash: excluded() = excluded_field()
    builtin: excluded() = excluded_field()
    id_type_both: excluded() = excluded_field()
    local: excluded() = excluded_field()
    immutable: excluded() = excluded_field()
    twofactor_auth_configured: excluded() = excluded_field()
    nt_name: excluded() = excluded_field()
    sid: excluded() = excluded_field()
    roles: excluded() = excluded_field()

    uid: Optional[Annotated[int, Ge(0), Le(TRUENAS_IDMAP_DEFAULT_LOW - 1)]] = None
    "UNIX UID. If not provided, it is automatically filled with the next one available."

    group_create: bool = False
    group: Optional[int] = None
    "Required if `group_create` is `false`."
    home_create: bool = False
    home_mode: str = "700"
    password: Private[Optional[str]] = None


class UserUpdate(UserCreate, metaclass=ForUpdateMetaclass):
    group_create: excluded() = excluded_field()


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
