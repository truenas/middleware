from middlewared.api.base import BaseModel, Private, single_argument_result
from middlewared.utils.auth import AuthMech, AuthResp
from typing import Literal
from .user import UserGetUserObjResult


class AuthMeArgs(BaseModel):
    pass


@single_argument_result
class AuthMeResult(UserGetUserObjResult.model_fields["result"].annotation):
    attributes: dict
    two_factor_config: dict
    privilege: dict
    account_attributes: list[str]


class AuthApiKeyPlain(BaseModel):
    mechanism: Literal[AuthMech.API_KEY_PLAIN.name]
    username: str
    api_key: Private[str]


class AuthPasswordPlain(BaseModel):
    mechanism: Literal[AuthMech.PASSWORD_PLAIN.name]
    username: str
    password: Private[str]


class AuthTokenPlain(BaseModel):
    mechanism: Literal[AuthMech.TOKEN_PLAIN.name]
    token: Private[str]


class AuthOTPToken(BaseModel):
    mechanism: Literal[AuthMech.OTP_TOKEN.name]
    otp_token: Private[str]


class AuthRespSuccess(BaseModel):
    response_type: Literal[AuthResp.SUCCESS.name]


class AuthRespAuthErr(BaseModel):
    response_type: Literal[AuthResp.AUTH_ERR.name]


class AuthRespExpired(BaseModel):
    response_type: Literal[AuthResp.EXPIRED.name]


class AuthRespOTPRequired(BaseModel):
    response_type: Literal[AuthResp.OTP_REQUIRED.name]
    username: str


class AuthLoginExArgs(BaseModel):
    login_data: AuthApiKeyPlain | AuthPasswordPlain | AuthTokenPlain | AuthOTPToken


class AuthLoginExResult(BaseModel):
    result: AuthRespSuccess | AuthRespAuthErr | AuthRespExpired | AuthRespOTPRequired
