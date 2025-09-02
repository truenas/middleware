import enum
import threading
from dataclasses import dataclass, asdict
from random import uniform
from time import monotonic
from .crypto import generate_string, sha512_crypt, check_unixhash

LEGACY_API_KEY_USERNAME = 'LEGACY_API_KEY'
MAX_OTP_ATTEMPTS = 3
AUID_UNSET = 2 ** 32 - 1
AUID_FAULTED = 2 ** 32 - 2


class AuthMech(enum.StrEnum):
    API_KEY_PLAIN = 'API_KEY_PLAIN'
    API_KEY_SCRAM = 'API_KEY_SCRAM'
    PASSWORD_PLAIN = 'PASSWORD_PLAIN'
    TOKEN_PLAIN = 'TOKEN_PLAIN'
    OTP_TOKEN = 'OTP_TOKEN'


class AuthResp(enum.StrEnum):
    SUCCESS = 'SUCCESS'
    AUTH_ERR = 'AUTH_ERR'
    EXPIRED = 'EXPIRED'
    OTP_REQUIRED = 'OTP_REQUIRED'
    REDIRECT = 'REDIRECT'
    SCRAM_RESPONSE = 'SCRAM_RESPONSE'


# NIST SP 800-63B provides documentation Authenticator Assurance Levels (AAL)
# https://nvlpubs.nist.gov/nistpubs/specialpublications/nist.sp.800-63b.pdf
#
# NIST SP 800-63-3 Section 6.2 provides guidance on how to select an AAL
# https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-63-3.pdf
@dataclass(frozen=True, slots=True)
class AuthenticatorAssuranceLevel:
    max_session_age: int
    max_inactivity: int | None
    mechanisms: tuple[AuthMech] | None
    otp_mandatory: bool
    min_fail_delay: int


@dataclass(slots=True)
class ServerAAL:
    level: AuthenticatorAssuranceLevel

    def get_delay_interval(self):
        return uniform(
            self.level.min_fail_delay,
            self.level.min_fail_delay + 1
        )


def aal_auth_mechanism_check(mechanism_str: str, aal: AuthenticatorAssuranceLevel) -> bool:
    """ This method checks whether the specified mechanism is permitted under the
    specified authenticator assurance level """
    mechanism = AuthMech[mechanism_str]

    if mechanism is AuthMech.OTP_TOKEN:
        # OTP tokens are always permitted
        return True

    return mechanism in aal.mechanisms


# NIST SP 800-63B Section 4.1 Authenticator Assurance Level 1
# Reauthentication should be performed every 30 days after which session should be
# logged out.
#
# NOTE: this is baseline for TrueNAS authentication
AA_LEVEL1 = AuthenticatorAssuranceLevel(
    max_session_age=86400 * 30,
    max_inactivity=None,
    mechanisms=(
        AuthMech.API_KEY_PLAIN,
        AuthMech.API_KEY_SCRAM,
        AuthMech.TOKEN_PLAIN,
        AuthMech.PASSWORD_PLAIN,
    ),
    otp_mandatory=False,
    min_fail_delay=1
)

# NIST SP 800-63B Section 4.2 Authenticator Assurance Level 2
# Reauthentication shall be performed at least once per 12 hours.
# Reauthentication shall be repeated after any period of inactivity lasting 30 minutes or longer.
#
# This level can be provided by using two single-factor authenticators. In this case a
# memorized secret (password) and OTP token. At least one factor _must_ be replay resistant,
# which is fulfilled by the OTP token.
#
# Per these guidelines, our TOKEN_PLAIN and API_KEY_PLAIN provide insufficient replay resistance,
# which is in addition to the replay-resistant nature of encrypted transport, and are therefore
# unsuitable for this authentication level.
AA_LEVEL2 = AuthenticatorAssuranceLevel(
    max_session_age=12 * 60 * 60,
    max_inactivity=30 * 60,
    mechanisms=(AuthMech.PASSWORD_PLAIN, AuthMech.API_KEY_SCRAM),
    otp_mandatory=True,
    min_fail_delay=4
)

# NIST SP 800-63B Section 4.3 Authenticator Assurance Level 3
# Reauthentication shall be performed at least once per 12 hours
# Reauthentication shall be repeated after any period of inactivity lasting 15 minutes or longer
AA_LEVEL3 = AuthenticatorAssuranceLevel(
    max_session_age=13 * 60,
    max_inactivity=15 * 60,
    mechanisms=(),
    otp_mandatory=True,
    min_fail_delay=4
)

CURRENT_AAL = ServerAAL(AA_LEVEL1)


class OTPWResponseCode(enum.StrEnum):
    SUCCESS = 'SUCCESS'
    EXPIRED = 'EXPIRED'
    NO_KEY = 'NO_KEY'
    ALREADY_USED = 'ALREADY_USED'
    WRONG_USER = 'WRONG_USER'
    BAD_PASSKEY = 'BAD_PASSKEY'


@dataclass(slots=True)
class UserOnetimePassword:
    uid: int   # UID of related user
    expires: int  # expiration time (monotonic)
    keyhash: str  # hash of onetime password
    used: bool = False  # whether password has been used for authentication
    password_set_override: bool = False  # whether we should allow override of password aging


@dataclass(slots=True)
class OTPWResponse:
    code: OTPWResponseCode
    data: dict | None = None  # asdict output of onetime password (if SUCCESS)


class OnetimePasswordManager:
    """
    This class stores passkeys that may be used precisely once to authenticate
    to the TrueNAS server as a particular user. This is to provide a mechanism
    for a system administrator to provision a temporary password for a user
    that may be used to set two-factor authentication and user password.
    """
    otpasswd = {}
    lock = threading.Lock()
    cnt = 0

    def generate_for_uid(self, uid: int, admin_generated: bool = False) -> str:
        """
        Generate a passkey for the given UID.

        Format is "<index in passkey list>_<plain text of passkey>"
        We store a sha512 hash of the plaintext for authentication purposes
        """
        with self.lock:
            p = generate_string(string_size=24)
            human_friendly = '-'.join([p[0:6], p[6:12], p[12:18], p[18:24]])
            keyhash = sha512_crypt(human_friendly)
            expires = monotonic() + 86400

            entry = UserOnetimePassword(
                uid=uid,
                expires=expires,
                keyhash=keyhash,
                password_set_override=admin_generated
            )
            self.cnt += 1
            self.otpasswd[str(self.cnt)] = entry
            return f'{self.cnt}_{human_friendly}'

    def authenticate(self, uid: int, plaintext: str) -> OTPWResponse:
        """ Check passkey matches plaintext string.  """
        try:
            idx, passwd = plaintext.split('_')
        except Exception:
            return OTPWResponse(OTPWResponseCode.NO_KEY)

        if (entry := self.otpasswd.get(idx)) is None:
            return OTPWResponse(OTPWResponseCode.NO_KEY)

        with self.lock:
            if entry.uid != uid:
                return OTPWResponse(OTPWResponseCode.WRONG_USER)

            if entry.used:
                return OTPWResponse(OTPWResponseCode.ALREADY_USED)

            if monotonic() > entry.expires:
                return OTPWResponse(OTPWResponseCode.EXPIRED)

            if not check_unixhash(passwd, entry.keyhash):
                return OTPWResponse(OTPWResponseCode.BAD_PASSKEY)

            entry.used = True

            return OTPWResponse(OTPWResponseCode.SUCCESS, asdict(entry))


OTPW_MANAGER = OnetimePasswordManager()


def get_login_uid(pid: int, raise_error=False) -> int:
    """
    Get the login uid of the specified PID. By design it is set by pam_loginuid
    on session login. If value is unitialized then the value will be UINT32_MAX -1
    Which is set as constant AUID_UNSET here and in auditd rules. If an error
    occurs during read then either the exception will be raised or the special
    value AUID_FAULTED (UINT32_MAX -2) will be returned (which is the default).
    """
    try:
        with open(f'/proc/{pid}/loginuid', 'r') as f:
            return int(f.read().strip())
    except Exception:
        if not raise_error:
            return AUID_FAULTED

        raise
