from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args


__all__ = [
    'TNCEntry', 'TNCGetRegistrationURIArgs', 'TNCGetRegistrationURIResult', 'TNCUpdateArgs', 'TNCUpdateResult',
    'TNCGenerateClaimTokenArgs', 'TNCGenerateClaimTokenResult', 'TNCIPChoicesArgs', 'TNCIPChoicesResult',
]


class TNCEntry(BaseModel):
    id: int
    enabled: bool
    jwt_token: NonEmptyString | None
    registration_details: dict
    ips: list[str]


@single_argument_args('tn_connect_update')
class TNCUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool


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
