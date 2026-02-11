import enum
from typing import Any

from string import punctuation
from .time_utils import datetime_to_epoch_days

# WARNING: Changes to MAX_PASSWORD_HISTORY may impact API schemas
# This value was chosen to be 2x beyond what is technically required
# for GPOS STIG.
MAX_PASSWORD_HISTORY = 10
SHADOW_SEPARATOR = ':'
GPOS_STIG_MIN_PASSWORD_AGE = 1  # SRG-OS-000075-GPOS-00043
GPOS_STIG_MAX_PASSWORD_AGE = 60  # SRG-OS-000076-GPOS-00044
GPOS_STIG_PASSWORD_REUSE_LIMIT = 5  # SRG-OS-000077-GPOS-00045
GPOS_STIG_PASSWORD_LENGTH = 15  # SRG-OS-000078-GPOS-00046
GPOS_STIG_MAX_USER_LOGINS = 10  # SRG-OS-000027-GPOS-00008

# The security plugin contains many options that are only
# available for enterprise-licensed users
ENTERPRISE_OPTIONS = frozenset([
    'enable_fips',
    'enable_gpos_stig',
    'min_password_age',
    'max_password_age',
    'password_complexity_ruleset',
    'min_password_length',
    'password_history_length',
])

PASSWORD_PROMPT_AGE = 6  # Number of days before expiry at which point we prompt for new password


class PasswordComplexity(enum.StrEnum):
    UPPER = 'UPPER'
    LOWER = 'LOWER'
    NUMBER = 'NUMBER'
    SPECIAL = 'SPECIAL'

    def check_password(self, password: str) -> bool:
        match self:
            case PasswordComplexity.UPPER:
                return any([char.isupper() for char in password])
            case PasswordComplexity.LOWER:
                return any([char.islower() for char in password])
            case PasswordComplexity.NUMBER:
                return any([char.isdigit() for char in password])
            case PasswordComplexity.SPECIAL:
                return any([char in punctuation for char in password])
            case _:
                raise ValueError(f'{self}: unhandled password complexity type')


# SRG-OS-000069-GPOS-00037
# SRG-OS-000070-GPOS-00038
# SRG-OS-000071-GPOS-00039
# SRG-OS-000266-GPOS-00101
GPOS_STIG_PASSWORD_COMPLEXITY = frozenset([
    PasswordComplexity.UPPER,
    PasswordComplexity.LOWER,
    PasswordComplexity.NUMBER,
    PasswordComplexity.SPECIAL,
])


class STIGType(enum.IntFlag):
    """
    Currently we are only attempting to meet a single STIG (General Purpose
    Operating System). This enum is defined so that we have capability
    to expand if we decide to apply more specific STIGs to different areas
    of our product
    """
    # https://www.stigviewer.com/stig/general_purpose_operating_system_srg/
    NONE = 0
    GPOS = enum.auto()  # General Purpose Operating System


def system_security_config_to_stig_type(config: dict[str, bool]) -> STIGType:
    return STIGType.GPOS if config['enable_gpos_stig'] else STIGType.NONE


def shadow_parse_aging(
    user: dict[str, Any],
    security: dict[str, Any],
    max_age_overrides: set[str] | None = None
) -> str:
    """
    Convert user entry to the password aging related portion of the shadow file

    Sample:

    <last change>:<min>:<max>:<warning>:<inactivity>:<expiration>:<reserved>

    params:
    -------
    user: dict, required
        user.query entry for shadow entry

    security: dict, required
        system.security.config results

    max_age_overrides: set, optional
        Set of usernames for which max_age restriction should not apply.
        This is used to prevent admin lockout to NAS.
    """
    max_age_skip_users = max_age_overrides or set()
    outstr = ''

    # Special cases
    if user['password_disabled']:
        # NAS-135872, NAS-135863: Prevent a password disabled account from being
        # disabled due to password change requirements.
        return '::::::'

    # man (5) shadow "date of last password change"
    # Expressed as number of days since Jan 1, 1970 00:00 UTC
    # The value of zero (0) has special meaning that password change is required
    # on next login.
    #
    # An empty field (for example if password has never been changed) means that
    # password aging is disabled for the account.
    if user['last_password_change'] is not None:
        outstr += str(datetime_to_epoch_days(user['last_password_change']))
    else:
        # We set timestamp on UI / API initiated password changes
        # unexpected None here should result in forcing password change
        # We cannot do this for the root account though because it will break
        # ability to su to root.
        #
        # NAS-135623 -- this check was relaxed to only set zero here if
        # password authentication is not disabled.
        if user['username'] != 'root' and not user['password_disabled']:
            outstr += '0'

    outstr += SHADOW_SEPARATOR

    if security['min_password_age']:
        outstr += str(security['min_password_age'])

    outstr += SHADOW_SEPARATOR

    if security['max_password_age'] and user['username'] not in max_age_skip_users:
        outstr += str(security['max_password_age'])

    outstr += SHADOW_SEPARATOR

    # Password warn period is not implemented due to limitations in
    # middleware / pam integration
    outstr += SHADOW_SEPARATOR

    # We do not currently implement password changes via pam / middleware
    # so this means hard cutoff on password expiration.
    outstr += '0'
    outstr += SHADOW_SEPARATOR

    # Account expiration date is not implemented due to problems
    # with passdb implementation
    outstr += SHADOW_SEPARATOR

    return outstr


def check_password_complexity(ruleset: set[str], password: str) -> set[PasswordComplexity]:
    unmet: set[PasswordComplexity] = set()

    if not isinstance(password, str):
        raise TypeError(f'{type(password)}: password expected to be string')

    if not isinstance(ruleset, set):
        raise TypeError(f'{type(ruleset)}: ruleset expected to be a set')

    for r in ruleset:
        rule = PasswordComplexity(r)
        if not rule.check_password(password):
            unmet.add(rule)

    return unmet
