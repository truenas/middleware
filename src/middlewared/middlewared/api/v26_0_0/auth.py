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
    username: str = Field(description="Username of the authenticated user.")
    login_id: str = Field(description="Unique identifier for the login.")
    login_at: datetime = Field(description="Timestamp of when the user logged in.")


class APIKeySessionData(BaseModel):
    id: int = Field(description="Unique identifier for the API key.")
    name: str = Field(description="Human-readable name of the API key.")


class APIKeyCredentialData(UserCredentialData):
    api_key: APIKeySessionData = Field(description="API key information used for authentication.")


class TokenCredentialData(BaseCredentialData):
    parent: 'TokenParentCredentialsData' = Field(description="Parent credential information that generated this token.")
    login_id: str = Field(description="Unique identifier for the login.")
    username: str | None = Field(description="Username associated with the token. `null` if not user-specific.")


class AuthSessionsEntry(BaseModel):
    id: str = Field(description="Unique identifier for the authentication session.")
    current: bool = Field(description="Whether this is the current active session.")
    internal: bool = Field(description="Whether this is an internal system session.")
    origin: str = Field(description="Origin information for the session (IP address, hostname, etc.).")
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'LOGIN_ONETIME_PASSWORD',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ] = Field(
        description=(
            "Authentication method used for this session.\n"
            "\n"
            "* `UNIX_SOCKET`: Local Unix domain socket authentication\n"
            "* `LOGIN_PASSWORD`: Username and password authentication\n"
            "* `LOGIN_TWOFACTOR`: Two-factor authentication login\n"
            "* `LOGIN_ONETIME_PASSWORD`: One-time password authentication\n"
            "* `API_KEY`: API key authentication\n"
            "* `TOKEN`: Token-based authentication\n"
            "* `TRUENAS_NODE`: TrueNAS cluster node authentication"
        ),
    )
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData = Field(
        description="Detailed credential information specific to the authentication method.",
    )
    created_at: datetime = Field(description="Timestamp when the session was created.")
    secure_transport: bool = Field(
        description="Whether the session was established over a secure transport (HTTPS/WSS).",
    )


class AuthCommonOptions(BaseModel):
    user_info: bool = Field(
        default=True,
        description="Whether to include detailed user information in the authentication response.",
    )  # include auth.me in successful result
    reconnect_token: bool = Field(
        default=False,
        description=(
            "Whether to include a reauthentication token in the authentication response. The `ttl` for the generated "
            "token depends on the TrueNAS webui setting for preferences->lifetime, with a default value of 600 seconds."
        ),
    )


class AuthApiKeyPlain(BaseModel):
    mechanism: Literal["API_KEY_PLAIN"] = Field(
        description="Authentication mechanism identifier for plain API key authentication.",
    )
    username: str = Field(description="Username associated with the API key.")
    api_key: Secret[str] = Field(description="API key for authentication.")
    login_options: AuthCommonOptions = Field(
        default=AuthCommonOptions(),
        description="Additional options for the authentication process.",
    )


class AuthLegacyUsernamePassword(BaseModel):
    username: str = Field(description="Username for authentication.")
    password: Secret[str] = Field(description="Password for authentication.")


class AuthOTPToken(BaseModel):
    mechanism: Literal["OTP_TOKEN"] = Field(
        description="Authentication mechanism identifier for one-time password tokens.",
    )
    otp_token: Secret[str] = Field(description="One-time password token for authentication.")
    login_options: AuthCommonOptions = Field(
        default=AuthCommonOptions(),
        description="Additional options for the authentication process.",
    )


class AuthPasswordPlain(BaseModel):
    mechanism: Literal["PASSWORD_PLAIN"] = Field(
        description="Authentication mechanism identifier for plain password authentication.",
    )
    username: str = Field(description="Username for authentication.")
    password: Secret[str] = Field(description="Password for authentication.")
    login_options: AuthCommonOptions = Field(
        default=AuthCommonOptions(),
        description="Additional options for the authentication process.",
    )


class AuthSCRAM(BaseModel):
    mechanism: Literal["SCRAM"] = Field(
        description=(
            "Authentication mechanism that implements SHA512-based RFC5802 authentication. The authentication mechanism"
            " provides replay resistence and capability for mutual validation of server and client sessions.\n"
            "\n"
            "The authentication mechanism is currently limited to API key credentials, but at a future point will be "
            "expanded to cover local user authentication.\n"
            "\n"
            "Channel binding support is also a planned enhancement of the authentication mechanism.\n"
            "\n"
            "C and python libraries to for managing the client-side portion of the authentication exchanges are "
            "provided at https://github.com/truenas/truenas_scram."
        ),
    )
    scram_type: Literal["CLIENT_FIRST_MESSAGE", "CLIENT_FINAL_MESSAGE"] = Field(
        description=(
            "Scram message type from client. The scram types indicate the message type that is represented by the "
            "`rfc_str` field. CLIENT_FIRST_MESSAGE - this corresponds with the client-first-message as defined in "
            "RFC5802. CLIENT_FINAL_MESSAGE - this corresponds with the client-final-message as defined in RFC5802."
        ),
    )
    rfc_str: str = Field(examples=[
        "n,,n=user,r=fyko+d2lbbFgONRv9qkxdawL",
        "c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts="
    ],
        description=(
            "This field contains the SCRAM authentication exchange message as defined in RFC5802. The expected format "
            "and contents depends on the `scram_type`. CLIENT_FIRST_MESSAGE: `n,,n=user:10,r=fyko+d2lbbFgONRv9qkxdawL` "
            "The `n,,` component indicates that client does not support channel bindings. `n=user:10` specifies the "
            "username and API key id (separated by `:` character). `r=fyko+d2lbbFgONRv9qkxdawL` specifies a "
            "base64-encoded nonce generated client-side. CLIENT_FINAL_MESSAGE: "
            "c=biws,r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j, p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts= `c=biws` contains "
            "channel binding information. In this example it's the base64-encoded string `n,,` (no channel binding "
            "support). `r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j` contains the combined client and server nonce as "
            "returned by the response to the CLIENT_FIRST_MESSAGE. `p=v0X8v3Bz2T0CJGbJQyF0X+HI4Ts=` contains the "
            "base64-encoded client proof generated based on client-side key material and client + server nonce."
        ))


class AuthRespAuthErr(BaseModel):
    response_type: Literal["AUTH_ERR"] = Field(
        description="Authentication response type indicating authentication failure.",
    )


class AuthRespAuthRedirect(BaseModel):
    response_type: Literal["REDIRECT"] = Field(
        description="Authentication response type indicating redirect is required.",
    )
    urls: list[str] = Field(description="Array of URLs to redirect to for authentication completion.")


class AuthRespExpired(BaseModel):
    response_type: Literal["EXPIRED"] = Field(
        description="Authentication response type indicating the session or token has expired.",
    )


class AuthRespDenied(BaseModel):
    response_type: Literal["DENIED"] = Field(
        description="Authentication response type indicating that the credential lacks API access.",
    )


class AuthRespOTPRequired(BaseModel):
    response_type: Literal["OTP_REQUIRED"] = Field(
        description="Authentication response type indicating one-time password is required.",
    )
    username: str = Field(description="Username for which OTP is required.")


class AuthUserInfo(UserGetUserObj):
    attributes: dict = Field(description="Custom user attributes and metadata.")
    two_factor_config: dict = Field(description="Two-factor authentication configuration for the user.")
    privilege: dict = Field(description="User privilege and role information.")
    account_attributes: list[str] = Field(description="Array of account attribute names available for this user.")


class AuthRespSuccess(BaseModel):
    response_type: Literal["SUCCESS"] = Field(description="Authentication response type indicating successful login.")
    user_info: AuthUserInfo | None = Field(description="Authenticated user information or `null` if not available.")
    authenticator: Literal['LEVEL_1', 'LEVEL_2'] = Field(
        description="Authentication level achieved (LEVEL_1 for password, LEVEL_2 for two-factor).",
    )
    reconnect_token: str | None = Field(
        description=(
            "Single-use token that can be used to reauthenticate to the truenas server in case websocket session is "
            "interrupted. This will be `null` in the following situations:\n"
            "\n"
            "1) The initiating authentication request set `reconnect_token` to `false` (default).\n"
            "2) The user authenticated via a one-time password, which does not support reconnect token creation."
        ),
    )


class AuthRespScram(BaseModel):
    response_type: Literal["SCRAM_RESPONSE"] = Field(
        description="Authentication response type indicating a SCRAM server response.",
    )
    scram_type: Literal["SERVER_FIRST_RESPONSE", "SERVER_FINAL_RESPONSE"] = Field(
        description=(
            "The type of server response. The SERVER_FIRST_RESPONSE will contain nonce, salt, and iterations. The "
            "SERVER_FINAL_RESPONSE will contain the server verification proof for client mutual validation."
        ),
    )
    rfc_str: str = Field(examples=[
        "r=fyko+d2lbbFgONRv9qkxdawL3rfcNHYJY1ZVvWVs7j,s=QSXCR+Q6sek8bf92,i=500000",
        "v=rmF9pqV8S7suAoZWja4dJRkFsKQ="
    ],
        description="Server authentication response containing string per RFC5802.")
    user_info: AuthUserInfo | None = Field(
        description="Authenticated user information on SERVER_FINAL_RESPONSE or null on SERVER_FIRST_RESPONSE.",
    )


class AuthTokenPlain(BaseModel):
    mechanism: Literal["TOKEN_PLAIN"] = Field(description="Authentication mechanism type for plain token login.")
    token: Secret[str] = Field(description="Authentication token (masked for security).")
    login_options: AuthCommonOptions = Field(
        default=AuthCommonOptions(),
        description="Common authentication options and settings.",
    )


class TokenParentCredentialsData(BaseModel):
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ] = Field(description="Type of credentials used to generate this token.")
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData = Field(
        description="Credential data used to authenticate the token request.",
    )


@single_argument_args('generate_single_use_password')
class AuthGenerateOnetimePasswordArgs(BaseModel):
    username: str = Field(description="Username to generate a one-time password for.")


class AuthGenerateOnetimePasswordResult(BaseModel):
    result: str = Field(description="Generated one-time password for the specified user.")


class AuthGenerateTokenArgs(BaseModel):
    ttl: int | None = Field(
        default=600,
        description="Time-to-live for the token in seconds or `null` for no expiration (default 600).",
    )
    attrs: dict = Field(
        default={},
        description="Additional attributes to embed in the token.",
    )  # XXX should we have some actual validation here?
    match_origin: bool = Field(
        default=True,
        description="Whether the token must be used from the same origin that created it.",
    )  # NOTE: this is change in default from before 25.04
    single_use: bool = Field(default=False, description="Whether the token can only be used once.")


class AuthGenerateTokenResult(BaseModel):
    result: str = Field(description="Generated authentication token.")


class AuthLoginArgs(AuthLegacyUsernamePassword):
    otp_token: Secret[str | None] = Field(
        default=None,
        description="One-time password token for two-factor authentication or `null`.",
    )


class AuthLoginResult(BaseModel):
    result: bool = Field(description="Returns `true` if login was successful, `false` otherwise.")


class AuthLoginExArgs(BaseModel):
    login_data: Union[
        AuthApiKeyPlain, AuthPasswordPlain, AuthTokenPlain, AuthOTPToken, AuthSCRAM
    ] = Field(discriminator='mechanism', description="Authentication data specifying mechanism and credentials.")


class AuthLoginExResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect,
        AuthRespScram, AuthRespDenied
    ] = Field(
        discriminator='response_type',
        description="Authentication response indicating success, failure, or additional steps required.",
    )


class AuthLoginExContinueArgs(BaseModel):
    login_data: AuthOTPToken = Field(description="OTP token data to continue two-factor authentication flow.")


class AuthLoginExContinueResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect,
        AuthRespDenied,
    ] = Field(discriminator='response_type', description="Authentication response after continuing with OTP token.")


class AuthLoginWithApiKeyArgs(BaseModel):
    api_key: Secret[str] = Field(description="API key for authentication (masked for security).")


class AuthLoginWithApiKeyResult(BaseModel):
    result: bool = Field(description="Returns `true` if API key login was successful, `false` otherwise.")


class AuthLoginWithTokenArgs(BaseModel):
    token: Secret[str] = Field(description="Authentication token (masked for security).")


class AuthLoginWithTokenResult(BaseModel):
    result: bool = Field(description="Returns `true` if token login was successful, `false` otherwise.")


class AuthMeArgs(BaseModel):
    pass


@single_argument_result
class AuthMeResult(AuthUserInfo):
    pass


class AuthMechanismChoicesArgs(BaseModel):
    pass


class AuthMechanismChoicesResult(BaseModel):
    result: list[str] = Field(description="Array of available authentication mechanisms.")


class AuthLogoutArgs(BaseModel):
    pass


class AuthLogoutResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when logout is successful.")


class AuthSetAttributeArgs(BaseModel):
    """WebUI attributes."""
    key: str = Field(description="Attribute key name.")
    value: Any = Field(description="Attribute value to set.")


class AuthSetAttributeResult(BaseModel):
    result: None = Field(description="Returns `null` when the attribute is successfully set.")


class AuthTerminateOtherSessionsArgs(BaseModel):
    pass


class AuthTerminateOtherSessionsResult(BaseModel):
    result: Literal[True] = Field(description="Returns `true` when other sessions are successfully terminated.")


class AuthTerminateSessionArgs(BaseModel):
    id: str = Field(description="Session ID to terminate.")


class AuthTerminateSessionResult(BaseModel):
    result: bool = Field(description="Returns `true` if the session was successfully terminated, `false` otherwise.")


class AuthSessionsAddedEvent(BaseModel):
    fields: AuthSessionsEntry = Field(description="Event fields.")


class AuthSessionsRemovedEvent(BaseModel):
    fields: "AuthSessionsRemovedEventFields" = Field(description="Event fields.")


class AuthSessionsRemovedEventFields(BaseModel):
    id: str = Field(description="Unique identifier for the authentication session.")
