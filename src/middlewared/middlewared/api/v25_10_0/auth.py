from middlewared.api.base import BaseModel, single_argument_args, single_argument_result
from middlewared.utils.auth import AuthMech, AuthResp
from datetime import datetime
from pydantic import Field, Secret
from typing import Any, ForwardRef, Literal
from .user import UserGetUserObjResult


class AuthMeArgs(BaseModel):
    pass


class AuthUserInfo(UserGetUserObjResult.model_fields["result"].annotation):
    attributes: dict
    two_factor_config: dict
    privilege: dict
    account_attributes: list[str]


class AuthLegacyUsernamePassword(BaseModel):
    username: str
    password: Secret[str]


class AuthLoginArgs(AuthLegacyUsernamePassword):
    otp_token: Secret[str | None] = None


class AuthLegacyApiKeyLoginArgs(BaseModel):
    api_key: Secret[str]


class AuthLegacyTokenLoginArgs(BaseModel):
    token: Secret[str]


class AuthLoginResult(BaseModel):
    result: bool


@single_argument_result
class AuthMeResult(AuthUserInfo):
    pass


class AuthCommonOptions(BaseModel):
    user_info: bool = True  # include auth.me in successful result


class AuthApiKeyPlain(BaseModel):
    mechanism: Literal[AuthMech.API_KEY_PLAIN]
    username: str
    api_key: Secret[str]
    login_options: AuthCommonOptions = Field(default=AuthCommonOptions())


class AuthPasswordPlain(BaseModel):
    mechanism: Literal[AuthMech.PASSWORD_PLAIN]
    username: str
    password: Secret[str]
    login_options: AuthCommonOptions = Field(default=AuthCommonOptions())


class AuthTokenPlain(BaseModel):
    mechanism: Literal[AuthMech.TOKEN_PLAIN]
    token: Secret[str]
    login_options: AuthCommonOptions = Field(default=AuthCommonOptions())


class AuthOTPToken(BaseModel):
    mechanism: Literal[AuthMech.OTP_TOKEN]
    otp_token: Secret[str]
    login_options: AuthCommonOptions = Field(default=AuthCommonOptions())


class AuthRespSuccess(BaseModel):
    response_type: Literal[AuthResp.SUCCESS]
    user_info: AuthUserInfo | None
    authenticator: Literal['LEVEL_1', 'LEVEL_2']


class AuthRespAuthErr(BaseModel):
    response_type: Literal[AuthResp.AUTH_ERR]


class AuthRespExpired(BaseModel):
    response_type: Literal[AuthResp.EXPIRED]


class AuthRespOTPRequired(BaseModel):
    response_type: Literal[AuthResp.OTP_REQUIRED]
    username: str


class AuthRespAuthRedirect(BaseModel):
    response_type: Literal[AuthResp.REDIRECT]
    urls: list[str]


class AuthLoginExArgs(BaseModel):
    login_data: AuthApiKeyPlain | AuthPasswordPlain | AuthTokenPlain | AuthOTPToken


class AuthLoginExContinueArgs(BaseModel):
    login_data: AuthOTPToken


class AuthLoginExResult(BaseModel):
    result: AuthRespSuccess | AuthRespAuthErr | AuthRespExpired | AuthRespOTPRequired | AuthRespAuthRedirect


class AuthMechChoicesArgs(BaseModel):
    pass


class AuthMechChoicesResult(BaseModel):
    result: list[str]


class BaseCredentialData(BaseModel):
    pass


class UserCredentialData(BaseCredentialData):
    username: str
    login_at: datetime


class APIKeySessionData(BaseModel):
    id: int
    name: str


class APIKeyCredentialData(UserCredentialData):
    api_key: APIKeySessionData


class TokenParentCredentialsData(BaseModel):
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ]
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | ForwardRef("TokenCredentialData")


class TokenCredentialData(BaseCredentialData):
    parent: TokenParentCredentialsData
    username: str | None


class AuthSessionEntry(BaseModel):
    id: str
    current: bool
    internal: bool
    origin: str
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ]
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData
    created_at: datetime
    secure_transport: bool


class AuthTerminateSessionArgs(BaseModel):
    id: str


class AuthTerminateSessionResult(BaseModel):
    result: bool


class AuthTerminateOtherSessionsArgs(BaseModel):
    pass


class AuthTerminateOtherSessionsResult(AuthTerminateSessionResult):
    result: Literal[True]


class AuthSessionLogoutArgs(BaseModel):
    pass


class AuthSessionLogoutResult(BaseModel):
    result: Literal[True]


class AuthGenerateTokenArgs(BaseModel):
    ttl: int | None = 600
    attrs: dict = {}  # XXX should we have some actual validation here?
    match_origin: bool = True  # NOTE: this is change in default from before 25.04
    single_use: bool = False


class AuthGenerateTokenResult(BaseModel):
    result: str


class AuthSetAttributeArgs(BaseModel):
    """ WebUI attributes """
    key: str
    value: Any


class AuthSetAttributeResult(BaseModel):
    result: Literal[None]


@single_argument_args('generate_single_use_password')
class AuthGenerateOnetimePasswordArgs(BaseModel):
    username: str


class AuthGenerateOnetimePasswordResult(BaseModel):
    result: str
