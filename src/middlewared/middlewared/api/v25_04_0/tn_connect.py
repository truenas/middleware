from typing import Annotated

from pydantic import HttpUrl, IPvAnyAddress, AfterValidator

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args
from middlewared.api.base.validators import https_only_check
from middlewared.utils.lang import undefined


__all__ = [
    'TNCEntry', 'TNCGetRegistrationURIArgs', 'TNCGetRegistrationURIResult', 'TNCUpdateArgs', 'TNCUpdateResult',
    'TNCGenerateClaimTokenArgs', 'TNCGenerateClaimTokenResult', 'TNCIPChoicesArgs', 'TNCIPChoicesResult',
]


HttpsURL = Annotated[HttpUrl, AfterValidator(https_only_check)]


class TNCEntry(BaseModel):
    id: int
    enabled: bool
    registration_details: dict
    ips: list[NonEmptyString]
    status: NonEmptyString
    status_reason: NonEmptyString
    certificate: int | None
    account_service_base_url: NonEmptyString
    leca_service_base_url: NonEmptyString
    tnc_base_url: NonEmptyString


@single_argument_args('tn_connect_update')
class TNCUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool
    ips: list[IPvAnyAddress]
    account_service_base_url: HttpsURL
    leca_service_base_url: HttpsURL
    tnc_base_url: HttpsURL


class TNCUpdateResult(BaseModel):
    result: TNCEntry


class TNCGetRegistrationURIArgs(BaseModel):
    pass


class TNCGetRegistrationURIResult(BaseModel):
    result: NonEmptyString


class TNCGenerateClaimTokenArgs(BaseModel):
    pass


class TNCGenerateClaimTokenResult(BaseModel):
    result: NonEmptyString


class TNCIPChoicesArgs(BaseModel):
    pass


class TNCIPChoicesResult(BaseModel):
    result: dict[str, str]
