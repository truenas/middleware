from pydantic import IPvAnyAddress

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args
from middlewared.api.base.types import HttpsOnlyURL


__all__ = [
    'TNCEntry', 'TNCGetRegistrationURIArgs', 'TNCGetRegistrationURIResult', 'TNCUpdateArgs', 'TNCUpdateResult',
    'TNCGenerateClaimTokenArgs', 'TNCGenerateClaimTokenResult', 'TNCIPChoicesArgs', 'TNCIPChoicesResult',
]


class TNCEntry(BaseModel):
    id: int
    enabled: bool
    registration_details: dict
    ips: list[NonEmptyString]
    status: NonEmptyString
    status_reason: NonEmptyString
    certificate: int | None
    account_service_base_url: HttpsOnlyURL
    leca_service_base_url: HttpsOnlyURL
    tnc_base_url: HttpsOnlyURL
    heartbeat_url: HttpsOnlyURL


@single_argument_args('tn_connect_update')
class TNCUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool
    ips: list[IPvAnyAddress]
    account_service_base_url: HttpsOnlyURL
    leca_service_base_url: HttpsOnlyURL
    tnc_base_url: HttpsOnlyURL
    heartbeat_url: HttpsOnlyURL


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
