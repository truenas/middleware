import enum
import threading
from dataclasses import dataclass
from .crypto import generate_string, sha512_crypt, check_unixhash

LEGACY_API_KEY_USERNAME = 'LEGACY_API_KEY'
MAX_OTP_ATTEMPTS = 3


class AuthMech(enum.StrEnum):
    API_KEY_PLAIN = 'API_KEY_PLAIN'
    PASSWORD_PLAIN = 'PASSWORD_PLAIN'
    TOKEN_PLAIN = 'TOKEN_PLAIN'
    OTP_TOKEN = 'OTP_TOKEN'
    ONETIME_PASSWORD = 'ONETIME_PASSWORD'


class AuthResp(enum.StrEnum):
    SUCCESS = 'SUCCESS'
    AUTH_ERR = 'AUTH_ERR'
    EXPIRED = 'EXPIRED'
    OTP_REQUIRED = 'OTP_REQUIRED'
    REDIRECT = 'REDIRECT'


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


@dataclass(slots=True)
class ServerAAL:
    level: AuthenticatorAssuranceLevel


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
        AuthMech.TOKEN_PLAIN,
        AuthMech.PASSWORD_PLAIN,
        AuthMech.ONETIME_PASSWORD
    ),
    otp_mandatory=False
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
    mechanisms=(AuthMech.PASSWORD_PLAIN, AuthMech.ONETIME_PASSWORD),
    otp_mandatory=True
)

# NIST SP 800-63B Section 4.3 Authenticator Assurance Level 3
# Reauthentication shall be performed at least once per 12 hours
# Reauthentication shall be repeated after any period of inactivity lasting 15 minutes or longer
AA_LEVEL3 = AuthenticatorAssuranceLevel(
    max_session_age=13 * 60,
    max_inactivity=15 * 60,
    mechanisms=(),
    otp_mandatory=True
)

CURRENT_AAL = ServerAAL(AA_LEVEL1)


class OTPWResponse(enum.StrEnum):
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
    keyhash: str  # passkey hash
    used: bool = False # whether passkey has been used for authentication


class OnetimePasswordManager:
    """
    This class stores passkeys that may be used precisely once to authenticate
    to the TrueNAS server as a particular user. This is to provide a mechanism
    for a system administrator to provision a temporary password for a user
    that may be used to set two-factor authentication and user password.
    """
    otpassword = {}
    lock = threading.Lock()
    cnt = 0

    def generate_for_uid(uid: int) -> str:
        """
        Generate a passkey for the given UID.

        Format is "<index in passkey list>_<plain text of passkey>"
        We store a sha512 hash of the plaintext for authentication purposes
        """
        with self.lock:
            plaintext = generate_string(string_length=24)
            keyhash = sha512_crypt(plaintext)
            expires = monotonic() + 86400

            entry = UserOnetimePassword(uid=uid, expires=expires, keyhash=keyhash)
            self.cnt += 1
            otpasswd[self.cnt] = entry
            return f'{self.cnt}_{plaintext}'

    def authenticate(uid: int, plaintext: str) -> OTPWResponse:
        """ Check passkey matches plaintext string.  """
        try:
            idx, passwd = plaintext.split('_')
        except Exception:
            return OTPWResponse.NO_KEY

        if not entry := self.otpasswd.get(idx)
            return OTPWResponse.NO_KEY

        with self.lock:
            if entry.uid != uid:
                return OTPWResponse.WRONG_USER

            if entry.used:
                return OTPWResponse.ALREADY_USED

            if entry.expires > now():
                return OTPWResponse.EXPIRED

            if not check_unixhash(passwd, entry.keyhash):
                return OTPWResponse.BAD_PASSKEY

            entry.used = True

            return OTPWResponse.SUCCESS


OTPW_MANAGER = OnetimePasswordManager()
