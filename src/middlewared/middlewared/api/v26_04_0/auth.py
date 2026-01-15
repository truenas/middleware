from datetime import datetime
from typing import Any, Literal, Union

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, single_argument_args, single_argument_result
from .user import UserGetUserObj


__all__ = [
    'AuthSessionsEntry', 'AuthGenerateOnetimePasswordArgs', 'AuthGenerateOnetimePasswordResult',
    'AuthGenerateTokenArgs', 'AuthGenerateTokenResult', 'AuthLoginArgs', 'AuthLoginResult', 'AuthLoginExArgs',
    'AuthLoginExResult', 'AuthLoginExContinueArgs', 'AuthLoginExContinueResult', 'AuthLoginWithApiKeyArgs',
    'AuthLoginWithApiKeyResult', 'AuthLoginWithTokenArgs', 'AuthLoginWithTokenResult', 'AuthMeArgs', 'AuthMeResult',
    'AuthMechanismChoicesArgs', 'AuthMechanismChoicesResult', 'AuthLogoutArgs', 'AuthLogoutResult',
    'AuthSetAttributeArgs', 'AuthSetAttributeResult', 'AuthTerminateOtherSessionsArgs',
    'AuthTerminateOtherSessionsResult', 'AuthTerminateSessionArgs', 'AuthTerminateSessionResult',
    'AuthSessionsAddedEvent', 'AuthSessionsRemovedEvent',
]


class BaseCredentialData(BaseModel):
    pass


class UserCredentialData(BaseCredentialData):
    username: str
    """Username of the authenticated user."""
    login_id: str
    """ Unique identifier for the login. """
    login_at: datetime
    """Timestamp of when the user logged in."""


class APIKeySessionData(BaseModel):
    id: int
    """Unique identifier for the API key."""
    name: str
    """Human-readable name of the API key."""


class APIKeyCredentialData(UserCredentialData):
    api_key: APIKeySessionData
    """API key information used for authentication."""


class TokenCredentialData(BaseCredentialData):
    parent: 'TokenParentCredentialsData'
    """Parent credential information that generated this token."""
    login_id: str
    """ Unique identifier for the login. """
    username: str | None
    """Username associated with the token. `null` if not user-specific."""


class AuthSessionsEntry(BaseModel):
    id: str
    """Unique identifier for the authentication session."""
    current: bool
    """Whether this is the current active session."""
    internal: bool
    """Whether this is an internal system session."""
    origin: str
    """Origin information for the session (IP address, hostname, etc.)."""
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'LOGIN_ONETIME_PASSWORD',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ]
    """Authentication method used for this session.

    * `UNIX_SOCKET`: Local Unix domain socket authentication
    * `LOGIN_PASSWORD`: Username and password authentication
    * `LOGIN_TWOFACTOR`: Two-factor authentication login
    * `LOGIN_ONETIME_PASSWORD`: One-time password authentication
    * `API_KEY`: API key authentication
    * `TOKEN`: Token-based authentication
    * `TRUENAS_NODE`: TrueNAS cluster node authentication
    """
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData
    """Detailed credential information specific to the authentication method."""
    created_at: datetime
    """Timestamp when the session was created."""
    secure_transport: bool
    """Whether the session was established over a secure transport (HTTPS/WSS)."""


class AuthCommonOptions(BaseModel):
    user_info: bool = True  # include auth.me in successful result
    """Whether to include detailed user information in the authentication response."""


class AuthApiKeyPlain(BaseModel):
    mechanism: Literal["API_KEY_PLAIN"]
    """Authentication mechanism identifier for plain API key authentication."""
    username: str
    """Username associated with the API key."""
    api_key: Secret[str]
    """API key for authentication."""
    login_options: AuthCommonOptions = AuthCommonOptions()
    """Additional options for the authentication process."""


class AuthLegacyUsernamePassword(BaseModel):
    username: str
    """Username for authentication."""
    password: Secret[str]
    """Password for authentication."""


class AuthOTPToken(BaseModel):
    mechanism: Literal["OTP_TOKEN"]
    """Authentication mechanism identifier for one-time password tokens."""
    otp_token: Secret[str]
    """One-time password token for authentication."""
    login_options: AuthCommonOptions = AuthCommonOptions()
    """Additional options for the authentication process."""


class AuthPasswordPlain(BaseModel):
    mechanism: Literal["PASSWORD_PLAIN"]
    """Authentication mechanism identifier for plain password authentication."""
    username: str
    """Username for authentication."""
    password: Secret[str]
    """Password for authentication."""
    login_options: AuthCommonOptions = AuthCommonOptions()
    """Additional options for the authentication process."""


class AuthSCRAM(BaseModel):
    mechanism: Literal["SCRAM"]
    """Authentication mechanism that implements SHA512-based RFC5802 authentication.
    The authentication mechanism provides replay resistence and capability for
    mutual validation of server and client sessions.

    The authentication mechanism is currently limited to API key credentials, but
    at a future point will be expanded to cover local user authentication.

    Channel binding support is also a planned enhancement of the authentication
    mechanism.

    C and python libraries to for managing the client-side portion of the authentication
    exchanges are provided at https://github.com/truenas/truenas_scram
    """
    scram_type: Literal["CLIENT_FIRST_MESSAGE", "CLIENT_FINAL_MESSAGE"]
    """Scram message type from client. The scram types indicate the message type that is represented by the \
    rfc_str` field.
    CLIENT_FIRST_MESSAGE - this corresponds with the client-first-message as defined in RFC5802.\
    CLIENT_FINAL_MESSAGE - this corresponds with the client-final-message as defined
    in RFC5802."""
    rfc_str: str = Field(examples=[
        "n,,n=user,r=fyko+d2lbbFgONRv9qkxdawL",
        "c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts="
    ])
    """This field contains the SCRAM authentication exchange message as defined in RFC5802.
    The expected format and contents depends on the `scram_type`.\
    CLIENT_FIRST_MESSAGE: `n,,n=user:10,r=fyko+d2lbbFgONRv9qkxdawL`\
    The `n,,` component indicates that client does not support channel bindings.
    `n=user:10` specifies the username and API key id (separated by `:` character).
    `r=fyko+d2lbbFgONRv9qkxdawL` specifies a base64-encoded nonce generated client-side.\

    CLIENT_FINAL_MESSAGE: c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,
    p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=\
    `c=biws` contains channel binding information. In this example it's the base64-encoded
    string `n,,` (no channel binding support).
    `r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j` contains the combined client and server
    nonce as returned by the response to the CLIENT_FIRST_MESSAGE.
    `p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=` contains the base64-encoded client proof generated
    based on client-side key material and client + server nonce.
    """


class AuthRespAuthErr(BaseModel):
    response_type: Literal["AUTH_ERR"]
    """Authentication response type indicating authentication failure."""


class AuthRespAuthRedirect(BaseModel):
    response_type: Literal["REDIRECT"]
    """Authentication response type indicating redirect is required."""
    urls: list[str]
    """Array of URLs to redirect to for authentication completion."""


class AuthRespExpired(BaseModel):
    response_type: Literal["EXPIRED"]
    """Authentication response type indicating the session or token has expired."""


class AuthRespOTPRequired(BaseModel):
    response_type: Literal["OTP_REQUIRED"]
    """Authentication response type indicating one-time password is required."""
    username: str
    """Username for which OTP is required."""


class AuthUserInfo(UserGetUserObj):
    attributes: dict
    """Custom user attributes and metadata."""
    two_factor_config: dict
    """Two-factor authentication configuration for the user."""
    privilege: dict
    """User privilege and role information."""
    account_attributes: list[str]
    """Array of account attribute names available for this user."""


class AuthRespSuccess(BaseModel):
    response_type: Literal["SUCCESS"]
    """Authentication response type indicating successful login."""
    user_info: AuthUserInfo | None
    """Authenticated user information or `null` if not available."""
    authenticator: Literal['LEVEL_1', 'LEVEL_2']
    """Authentication level achieved (LEVEL_1 for password, LEVEL_2 for two-factor)."""


class AuthRespScram(BaseModel):
    response_type: Literal["SCRAM_RESPONSE"]
    """Authentication response type indicating a SCRAM server response."""
    scram_type: Literal["SERVER_FIRST_RESPONSE", "SERVER_FINAL_RESPONSE"]
    """The type of server response. The SERVER_FIRST_RESPONSE will contain nonce, salt,\
    and iterations. The SERVER_FINAL_RESPONSE will contain the server verification proof\
    for client mutual validation."""
    rfc_str: str = Field(examples=[
        "r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=QSXCR+Q6sek8bf92,i=500000",
        "v=rmF9pqV8S7suAoZWja4dJRkFsKQ="
    ])
    """Server authentication response containing string per RFC5802."""
    user_info: AuthUserInfo | None
    """Authenticated user information on SERVER_FINAL_RESPONSE or null on SERVER_FIRST_RESPONSE."""


class AuthTokenPlain(BaseModel):
    mechanism: Literal["TOKEN_PLAIN"]
    """Authentication mechanism type for plain token login."""
    token: Secret[str]
    """Authentication token (masked for security)."""
    login_options: AuthCommonOptions = AuthCommonOptions()
    """Common authentication options and settings."""


class TokenParentCredentialsData(BaseModel):
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ]
    """Type of credentials used to generate this token."""
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData
    """Credential data used to authenticate the token request."""


@single_argument_args('generate_single_use_password')
class AuthGenerateOnetimePasswordArgs(BaseModel):
    username: str
    """Username to generate a one-time password for."""


class AuthGenerateOnetimePasswordResult(BaseModel):
    result: str
    """Generated one-time password for the specified user."""


class AuthGenerateTokenArgs(BaseModel):
    ttl: int | None = 600
    """Time-to-live for the token in seconds or `null` for no expiration (default 600)."""
    attrs: dict = {}  # XXX should we have some actual validation here?
    """Additional attributes to embed in the token."""
    match_origin: bool = True  # NOTE: this is change in default from before 25.04
    """Whether the token must be used from the same origin that created it."""
    single_use: bool = False
    """Whether the token can only be used once."""


class AuthGenerateTokenResult(BaseModel):
    result: str
    """Generated authentication token."""


class AuthLoginArgs(AuthLegacyUsernamePassword):
    otp_token: Secret[str | None] = None
    """One-time password token for two-factor authentication or `null`."""


class AuthLoginResult(BaseModel):
    result: bool
    """Returns `true` if login was successful, `false` otherwise."""


class AuthLoginExArgs(BaseModel):
    login_data: Union[
        AuthApiKeyPlain, AuthPasswordPlain, AuthTokenPlain, AuthOTPToken, AuthSCRAM
    ] = Field(discriminator='mechanism')
    """Authentication data specifying mechanism and credentials."""


class AuthLoginExResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect,
        AuthRespScram
    ] = Field(discriminator='response_type')
    """Authentication response indicating success, failure, or additional steps required."""


class AuthLoginExContinueArgs(BaseModel):
    login_data: AuthOTPToken
    """OTP token data to continue two-factor authentication flow."""


class AuthLoginExContinueResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect
    ] = Field(discriminator='response_type')
    """Authentication response after continuing with OTP token."""


class AuthLoginWithApiKeyArgs(BaseModel):
    api_key: Secret[str]
    """API key for authentication (masked for security)."""


class AuthLoginWithApiKeyResult(BaseModel):
    result: bool
    """Returns `true` if API key login was successful, `false` otherwise."""


class AuthLoginWithTokenArgs(BaseModel):
    token: Secret[str]
    """Authentication token (masked for security)."""


class AuthLoginWithTokenResult(BaseModel):
    result: bool
    """Returns `true` if token login was successful, `false` otherwise."""


class AuthMeArgs(BaseModel):
    pass


@single_argument_result
class AuthMeResult(AuthUserInfo):
    pass


class AuthMechanismChoicesArgs(BaseModel):
    pass


class AuthMechanismChoicesResult(BaseModel):
    result: list[str]
    """Array of available authentication mechanisms."""


class AuthLogoutArgs(BaseModel):
    pass


class AuthLogoutResult(BaseModel):
    result: Literal[True]
    """Returns `true` when logout is successful."""


class AuthSetAttributeArgs(BaseModel):
    """WebUI attributes."""
    key: str
    """Attribute key name."""
    value: Any
    """Attribute value to set."""


class AuthSetAttributeResult(BaseModel):
    result: None
    """Returns `null` when the attribute is successfully set."""


class AuthTerminateOtherSessionsArgs(BaseModel):
    pass


class AuthTerminateOtherSessionsResult(BaseModel):
    result: Literal[True]
    """Returns `true` when other sessions are successfully terminated."""


class AuthTerminateSessionArgs(BaseModel):
    id: str
    """Session ID to terminate."""


class AuthTerminateSessionResult(BaseModel):
    result: bool
    """Returns `true` if the session was successfully terminated, `false` otherwise."""


class AuthSessionsAddedEvent(BaseModel):
    fields: AuthSessionsEntry
    """Event fields."""


class AuthSessionsRemovedEvent(BaseModel):
    fields: "AuthSessionsRemovedEventFields"
    """Event fields."""


class AuthSessionsRemovedEventFields(BaseModel):
    id: str
    """Unique identifier for the authentication session."""
