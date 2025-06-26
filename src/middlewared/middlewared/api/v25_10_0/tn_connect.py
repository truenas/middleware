from pydantic import IPvAnyAddress

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args
from middlewared.api.base.types import HttpsOnlyURL


__all__ = [
    'TNCEntry', 'TrueNASConnectGetRegistrationUriArgs', 'TrueNASConnectGetRegistrationUriResult',
    'TrueNASConnectUpdateArgs', 'TrueNASConnectUpdateResult',
    'TrueNASConnectGenerateClaimTokenArgs', 'TrueNASConnectGenerateClaimTokenResult',
    'TrueNASConnectIpChoicesArgs', 'TrueNASConnectIpChoicesResult',
]


class TNCEntry(BaseModel):
    id: int
    enabled: bool
    registration_details: dict
    ips: list[NonEmptyString]
    interfaces: list[str]
    interfaces_ips: list[str]
    status: NonEmptyString
    status_reason: NonEmptyString
    certificate: int | None
    account_service_base_url: HttpsOnlyURL
    leca_service_base_url: HttpsOnlyURL
    tnc_base_url: HttpsOnlyURL
    heartbeat_url: HttpsOnlyURL


@single_argument_args('tn_connect_update')
class TrueNASConnectUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool
    ips: list[IPvAnyAddress]
    interfaces: list[str]
    account_service_base_url: HttpsOnlyURL
    leca_service_base_url: HttpsOnlyURL
    tnc_base_url: HttpsOnlyURL
    heartbeat_url: HttpsOnlyURL


class TrueNASConnectUpdateResult(BaseModel):
    result: TNCEntry


class TrueNASConnectGetRegistrationUriArgs(BaseModel):
    pass


class TrueNASConnectGetRegistrationUriResult(BaseModel):
    result: NonEmptyString


class TrueNASConnectGenerateClaimTokenArgs(BaseModel):
    pass


class TrueNASConnectGenerateClaimTokenResult(BaseModel):
    result: NonEmptyString


class TrueNASConnectIpChoicesArgs(BaseModel):
    pass


class TrueNASConnectIpChoicesResult(BaseModel):
    result: dict[str, str]
