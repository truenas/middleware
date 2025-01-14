from pydantic import IPvAnyAddress, model_validator

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args
from middlewared.utils.lang import undefined


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
    account_service_base_url: NonEmptyString
    leca_service_base_url: NonEmptyString
    tnc_base_url: NonEmptyString


@single_argument_args('tn_connect_update')
class TNCUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool
    ips: list[IPvAnyAddress]
    account_service_base_url: NonEmptyString
    leca_service_base_url: NonEmptyString
    tnc_base_url: NonEmptyString

    @model_validator(mode='after')
    def validate_attrs(self):
        for k in ('account_service_base_url', 'leca_service_base_url', 'tnc_base_url'):
            value = getattr(self, k)
            if value != undefined and not value.startswith('https://'):
                raise ValueError(f'{k} must start with https://')
            if value != undefined and not value.endswith('/'):
                setattr(self, k, value + '/')
        return self


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
