from datetime import datetime
from typing import Any, Literal, Union

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, single_argument_args, single_argument_result
from middlewared.utils.auth import AuthMech, AuthResp
from .user import UserGetUserObj


__all__ = [
    'AuthSessionsEntry', 'AuthGenerateOnetimePasswordArgs', 'AuthGenerateOnetimePasswordResult',
    'AuthGenerateTokenArgs', 'AuthGenerateTokenResult', 'AuthLoginArgs', 'AuthLoginResult', 'AuthLoginExArgs',
    'AuthLoginExResult', 'AuthLoginExContinueArgs', 'AuthLoginExContinueResult', 'AuthLoginWithApiKeyArgs',
    'AuthLoginWithApiKeyResult', 'AuthLoginWithTokenArgs', 'AuthLoginWithTokenResult', 'AuthMeArgs', 'AuthMeResult',
    'AuthMechanismChoicesArgs', 'AuthMechanismChoicesResult', 'AuthLogoutArgs', 'AuthLogoutResult',
    'AuthSetAttributeArgs', 'AuthSetAttributeResult', 'AuthTerminateOtherSessionsArgs',
    'AuthTerminateOtherSessionsResult', 'AuthTerminateSessionArgs', 'AuthTerminateSessionResult',
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
    mechanism: Literal[AuthMech.API_KEY_PLAIN]
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
    mechanism: Literal[AuthMech.OTP_TOKEN]
    """Authentication mechanism identifier for one-time password tokens."""
    otp_token: Secret[str]
    """One-time password token for authentication."""
    login_options: AuthCommonOptions = AuthCommonOptions()
    """Additional options for the authentication process."""


class AuthPasswordPlain(BaseModel):
    mechanism: Literal[AuthMech.PASSWORD_PLAIN]
    """Authentication mechanism identifier for plain password authentication."""
    username: str
    """Username for authentication."""
    password: Secret[str]
    """Password for authentication."""
    login_options: AuthCommonOptions = AuthCommonOptions()
    """Additional options for the authentication process."""


class AuthRespAuthErr(BaseModel):
    response_type: Literal[AuthResp.AUTH_ERR]
    """Authentication response type indicating authentication failure."""


class AuthRespAuthRedirect(BaseModel):
    response_type: Literal[AuthResp.REDIRECT]
    """Authentication response type indicating redirect is required."""
    urls: list[str]
    """Array of URLs to redirect to for authentication completion."""


class AuthRespExpired(BaseModel):
    response_type: Literal[AuthResp.EXPIRED]
    """Authentication response type indicating the session or token has expired."""


class AuthRespOTPRequired(BaseModel):
    response_type: Literal[AuthResp.OTP_REQUIRED]
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
    response_type: Literal[AuthResp.SUCCESS]
    """Authentication response type indicating successful login."""
    user_info: AuthUserInfo | None
    """Authenticated user information or `null` if not available."""
    authenticator: Literal['LEVEL_1', 'LEVEL_2']
    """Authentication level achieved (LEVEL_1 for password, LEVEL_2 for two-factor)."""


class AuthTokenPlain(BaseModel):
    mechanism: Literal[AuthMech.TOKEN_PLAIN]
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
    login_data: AuthApiKeyPlain | AuthPasswordPlain | AuthTokenPlain | AuthOTPToken = Field(discriminator='mechanism')
    """Authentication data specifying mechanism and credentials."""


class AuthLoginExResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect
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
