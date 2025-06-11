from typing import Annotated, Literal

from pydantic import PositiveInt, Field

from middlewared.api.base import (
    BaseModel,
    Excluded,
    excluded_field,
    ForUpdateMetaclass,
    single_argument_args
)
from middlewared.utils.security import PasswordComplexity, MAX_PASSWORD_HISTORY


__all__ = [
    'SystemSecurityEntry', 'SystemSecurityUpdateArgs', 'SystemSecurityUpdateResult',
    'SystemSecurityInfoFipsAvailableArgs', 'SystemSecurityInfoFipsAvailableResult',
    'SystemSecurityInfoFipsEnabledArgs', 'SystemSecurityInfoFipsEnabledResult',
]


PASSWORD_COMPLEXITY_CHOICES = Literal[
    PasswordComplexity.UPPER,
    PasswordComplexity.LOWER,
    PasswordComplexity.NUMBER,
    PasswordComplexity.SPECIAL,
]


class SystemSecurityEntry(BaseModel):
    id: int
    enable_fips: bool
    """ When set, enables FIPS mode. """
    enable_gpos_stig: bool
    """ When set, enables compatibility with the General Purpose Operating System STIG. """
    min_password_age: PositiveInt | None = None
    """
    The number of days local users will have to wait before they will be
    allowed to change password again. One reason for setting this parameter is
    to prevent users from bypassing password history restrictions by rapidly
    changing their passwords. The value of None means that there is no
    minimum password age.
    """
    max_password_age: Annotated[int, Field(ge=7, le=365)] | None = None
    """
    The number of days after which a password is considered to be expired. After
    expiration no login will be possible for the user. The user should contact the
    administrator for a password reset. The value of None means that there is no
    maximum password age, and password aging is disabled. NOTE: user passwords will never
    expire if password aging is disabled.
    """
    password_complexity_ruleset: set[PASSWORD_COMPLEXITY_CHOICES] | None = None
    """
    The password complexity ruleset defines what character types are required
    for passwords used by local accounts. The value of None means that there
    are no password complexity requirements. List items indicate a requirement
    for at least one character in the password to be of the specified character
    set type.
    """
    min_password_length: Annotated[int, Field(ge=8)] | None = None
    """
    The minimum length of passwords used for local accounts. The value of None
    means that there is no minimum password length.
    """
    password_history_length: Annotated[int, Field(ge=1, le=MAX_PASSWORD_HISTORY)] | None = None
    """
    The number of password generations to keep in history for checks against
    password reuse for local user accounts. The value of None means that history checks
    for password reuse are not performed.
    """


@single_argument_args('system_security_update')
class SystemSecurityUpdateArgs(SystemSecurityEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class SystemSecurityUpdateResult(BaseModel):
    result: SystemSecurityEntry


class SystemSecurityInfoFipsAvailableArgs(BaseModel):
    pass


class SystemSecurityInfoFipsAvailableResult(BaseModel):
    result: bool


class SystemSecurityInfoFipsEnabledArgs(BaseModel):
    pass


class SystemSecurityInfoFipsEnabledResult(BaseModel):
    result: bool
