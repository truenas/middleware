from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args


__all__ = [
    'TNCEntry', 'TNCGetRegistrationURIArgs', 'TNCGetRegistrationURIResult', 'TNCUpdateArgs', 'TNCUpdateResult',
    'TNCGenerateClaimTokenArgs', 'TNCGenerateClaimTokenResult',
]


class TNCEntry(BaseModel):
    id: int
    enabled: bool
    claim_token: NonEmptyString | None
    jwt_token: NonEmptyString | None
    claim_token_system_id: NonEmptyString | None
    jwt_token_system_id: NonEmptyString | None
    acme_key: NonEmptyString | None
    acme_account_uri: NonEmptyString | None
    acme_directory_uri: NonEmptyString | None
    jwt_details: dict
    ip: str | None


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
