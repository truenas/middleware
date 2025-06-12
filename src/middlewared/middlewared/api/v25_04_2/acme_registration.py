from pydantic import Field

from middlewared.api.base import BaseModel, LongString, single_argument_args


__all__ = [
    'ACMERegistrationCreateArgs', 'ACMERegistrationCreateResult', 'ACMERegistrationEntry',
]


class JWKCreate(BaseModel):
    key_size: int = 2048
    public_exponent: int = 65537


class ACMERegistrationBody(BaseModel):
    id: int
    status: str
    key: LongString


class ACMERegistrationEntry(BaseModel):
    id: int
    uri: str
    directory: str
    tos: str
    new_account_uri: str
    new_nonce_uri: str
    new_order_uri: str
    revoke_cert_uri: str
    body: ACMERegistrationBody


@single_argument_args('acme_registration_create')
class ACMERegistrationCreateArgs(BaseModel):
    tos: bool = False
    JWK_create: JWKCreate = Field(default=JWKCreate())
    acme_directory_uri: str


class ACMERegistrationCreateResult(BaseModel):
    result: ACMERegistrationEntry
