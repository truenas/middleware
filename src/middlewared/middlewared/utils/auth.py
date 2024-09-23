import enum
from dataclasses import dataclass

LEGACY_API_KEY_USERNAME = 'LEGACY_API_KEY'
MAX_OTP_ATTEMPTS = 3


class AuthMech(enum.Enum):
    API_KEY_PLAIN = enum.auto()
    PASSWORD_PLAIN = enum.auto()
    TOKEN_PLAIN = enum.auto()
    OTP_TOKEN = enum.auto()


class AuthResp(enum.Enum):
    SUCCESS = enum.auto()
    AUTH_ERR = enum.auto()
    EXPIRED = enum.auto()
    OTP_REQUIRED = enum.auto()


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
    mechanisms=(AuthMech.API_KEY_PLAIN, AuthMech.TOKEN_PLAIN, AuthMech.PASSWORD_PLAIN),
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
    mechanisms=(AuthMech.PASSWORD_PLAIN,),
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
