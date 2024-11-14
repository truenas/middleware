from middlewared.api.base import BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args


__all__ = [
    'TNCEntry', 'TNCGetRegistrationURIArgs', 'TNCGetRegistrationURIResult', 'TNCUpdateArgs', 'TNCUpdateResult',
]


class TNCEntry(BaseModel):
    id: int
    enabled: bool
    claim_token: NonEmptyString | None
    jwt_token: NonEmptyString | None
    system_id: NonEmptyString | None
    acme_key: NonEmptyString | None
    acme_account_uri: NonEmptyString | None
    acme_directory_uri: NonEmptyString | None


@single_argument_args('tn_connect_update')
class TNCUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    enabled: bool


class TNCUpdateResult(BaseModel):
    result: TNCEntry


class TNCGetRegistrationURIArgs(BaseModel):
    pass


class TNCGetRegistrationURIResult(BaseModel):
    result: NonEmptyString
