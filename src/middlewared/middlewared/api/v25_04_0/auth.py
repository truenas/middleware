from middlewared.api.base import BaseModel, single_argument_result
from middlewared.utils.auth import AuthMech, AuthResp
from pydantic import Field, Secret
from typing import Literal
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


class AuthLegacyTwoFactorArgs(AuthLegacyUsernamePassword):
    pass


class AuthLegacyPasswordLoginArgs(AuthLegacyUsernamePassword):
    otp_token: Secret[str | None] = None


class AuthLegacyApiKeyLoginArgs(BaseModel):
    api_key: Secret[str]


class AuthLegacyTokenLoginArgs(BaseModel):
    token: Secret[str]


class AuthLegacyResult(BaseModel):
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


class AuthRespAuthErr(BaseModel):
    response_type: Literal[AuthResp.AUTH_ERR]


class AuthRespExpired(BaseModel):
    response_type: Literal[AuthResp.EXPIRED]


class AuthRespOTPRequired(BaseModel):
    response_type: Literal[AuthResp.OTP_REQUIRED]
    username: str


class AuthLoginExArgs(BaseModel):
    login_data: AuthApiKeyPlain | AuthPasswordPlain | AuthTokenPlain | AuthOTPToken


class AuthLoginExResult(BaseModel):
    result: AuthRespSuccess | AuthRespAuthErr | AuthRespExpired | AuthRespOTPRequired


class AuthMechChoicesArgs(BaseModel):
    pass


class AuthMechChoicesResult(BaseModel):
    result: list[str]
