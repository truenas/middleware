import enum

LEGACY_API_KEY_USERNAME = '.LEGACY_API_KEY'


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
