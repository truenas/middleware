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
    login_at: datetime


class APIKeySessionData(BaseModel):
    id: int
    name: str


class APIKeyCredentialData(UserCredentialData):
    api_key: APIKeySessionData


class TokenCredentialData(BaseCredentialData):
    parent: 'TokenParentCredentialsData'
    username: str | None


class AuthSessionsEntry(BaseModel):
    id: str
    current: bool
    internal: bool
    origin: str
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'LOGIN_ONETIME_PASSWORD',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ]
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData
    created_at: datetime
    secure_transport: bool


class AuthCommonOptions(BaseModel):
    user_info: bool = True  # include auth.me in successful result


class AuthApiKeyPlain(BaseModel):
    mechanism: Literal[AuthMech.API_KEY_PLAIN]
    username: str
    api_key: Secret[str]
    login_options: AuthCommonOptions = AuthCommonOptions()


class AuthLegacyUsernamePassword(BaseModel):
    username: str
    password: Secret[str]


class AuthOTPToken(BaseModel):
    mechanism: Literal[AuthMech.OTP_TOKEN]
    otp_token: Secret[str]
    login_options: AuthCommonOptions = AuthCommonOptions()


class AuthPasswordPlain(BaseModel):
    mechanism: Literal[AuthMech.PASSWORD_PLAIN]
    username: str
    password: Secret[str]
    login_options: AuthCommonOptions = AuthCommonOptions()


class AuthRespAuthErr(BaseModel):
    response_type: Literal[AuthResp.AUTH_ERR]


class AuthRespAuthRedirect(BaseModel):
    response_type: Literal[AuthResp.REDIRECT]
    urls: list[str]


class AuthRespExpired(BaseModel):
    response_type: Literal[AuthResp.EXPIRED]


class AuthRespOTPRequired(BaseModel):
    response_type: Literal[AuthResp.OTP_REQUIRED]
    username: str


class AuthUserInfo(UserGetUserObj):
    attributes: dict
    two_factor_config: dict
    privilege: dict
    account_attributes: list[str]


class AuthRespSuccess(BaseModel):
    response_type: Literal[AuthResp.SUCCESS]
    user_info: AuthUserInfo | None
    authenticator: Literal['LEVEL_1', 'LEVEL_2']


class AuthTokenPlain(BaseModel):
    mechanism: Literal[AuthMech.TOKEN_PLAIN]
    token: Secret[str]
    login_options: AuthCommonOptions = AuthCommonOptions()


class TokenParentCredentialsData(BaseModel):
    credentials: Literal[
        'UNIX_SOCKET',
        'LOGIN_PASSWORD',
        'LOGIN_TWOFACTOR',
        'API_KEY',
        'TOKEN',
        'TRUENAS_NODE',
    ]
    credentials_data: BaseCredentialData | UserCredentialData | APIKeyCredentialData | TokenCredentialData


@single_argument_args('generate_single_use_password')
class AuthGenerateOnetimePasswordArgs(BaseModel):
    username: str


class AuthGenerateOnetimePasswordResult(BaseModel):
    result: str


class AuthGenerateTokenArgs(BaseModel):
    ttl: int | None = 600
    attrs: dict = {}  # XXX should we have some actual validation here?
    match_origin: bool = True  # NOTE: this is change in default from before 25.04
    single_use: bool = False


class AuthGenerateTokenResult(BaseModel):
    result: str


class AuthLoginArgs(AuthLegacyUsernamePassword):
    otp_token: Secret[str | None] = None


class AuthLoginResult(BaseModel):
    result: bool


class AuthLoginExArgs(BaseModel):
    login_data: AuthApiKeyPlain | AuthPasswordPlain | AuthTokenPlain | AuthOTPToken = Field(discriminator='mechanism')


class AuthLoginExResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect
    ] = Field(discriminator='response_type')


class AuthLoginExContinueArgs(BaseModel):
    login_data: AuthOTPToken


class AuthLoginExContinueResult(BaseModel):
    result: Union[
        AuthRespSuccess, AuthRespAuthErr, AuthRespExpired, AuthRespOTPRequired, AuthRespAuthRedirect
    ] = Field(discriminator='response_type')


class AuthLoginWithApiKeyArgs(BaseModel):
    api_key: Secret[str]


class AuthLoginWithApiKeyResult(BaseModel):
    result: bool


class AuthLoginWithTokenArgs(BaseModel):
    token: Secret[str]


class AuthLoginWithTokenResult(BaseModel):
    result: bool


class AuthMeArgs(BaseModel):
    pass


@single_argument_result
class AuthMeResult(AuthUserInfo):
    pass


class AuthMechanismChoicesArgs(BaseModel):
    pass


class AuthMechanismChoicesResult(BaseModel):
    result: list[str]


class AuthLogoutArgs(BaseModel):
    pass


class AuthLogoutResult(BaseModel):
    result: Literal[True]


class AuthSetAttributeArgs(BaseModel):
    """WebUI attributes"""
    key: str
    value: Any


class AuthSetAttributeResult(BaseModel):
    result: Literal[None]


class AuthTerminateOtherSessionsArgs(BaseModel):
    pass


class AuthTerminateOtherSessionsResult(BaseModel):
    result: Literal[True]


class AuthTerminateSessionArgs(BaseModel):
    id: str


class AuthTerminateSessionResult(BaseModel):
    result: bool
