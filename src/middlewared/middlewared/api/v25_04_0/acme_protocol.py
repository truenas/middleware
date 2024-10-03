from typing import Literal

from pydantic import Field, Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, single_argument_args
from middlewared.plugins.acme_protocol_.authenticators.factory import auth_factory


__all__ = [
    'ACMERegistrationCreateArgs', 'ACMERegistrationCreateResult', 'DNSAuthenticatorUpdateArgs',
    'DNSAuthenticatorUpdateResult', 'DNSAuthenticatorCreateArgs', 'DNSAuthenticatorCreateResult',
    'DNSAuthenticatorDeleteArgs', 'DNSAuthenticatorDeleteResult', 'DNSAuthenticatorSchemasArgs',
    'DNSAuthenticatorSchemasResult', 'ACMERegistrationEntry', 'ACMEDNSAuthenticatorEntry',
]


class JWKCreate(BaseModel):
    key_size: int = 2048
    public_exponent: int = 65537


class ACMERegistrationEntry(BaseModel):
    id: int
    uri: str
    directory: str
    tos: str
    new_account_uri: str
    new_nonce_uri: str
    new_order_uri: str
    revoke_cert_uri: str


class ACMEDNSAuthenticatorEntry(BaseModel):
    id: int
    authenticator: Literal[tuple(auth_factory.get_authenticators())]
    attributes: Secret[dict]
    name: str


class DNSAuthenticatorCreate(ACMEDNSAuthenticatorEntry):
    id: Excluded = excluded_field()


class DNSAuthenticatorUpdate(DNSAuthenticatorCreate):
    authenticator: Excluded = excluded_field()


class DNSAuthenticatorAttributeSchema(BaseModel):
    _name_: str
    title: str
    _required_: bool


class DNSAuthenticatorSchemaEntry(BaseModel):
    key: str
    schema: list[DNSAuthenticatorAttributeSchema]


###################   Arguments   ###################


@single_argument_args('acme_registration_create')
class ACMERegistrationCreateArgs(BaseModel):
    tos: bool = False
    jwk_create: JWKCreate = Field(default=JWKCreate())
    acme_directory_uri: str


class DNSAuthenticatorCreateArgs(BaseModel):
    dns_authenticator_create: DNSAuthenticatorCreate


class DNSAuthenticatorUpdateArgs(BaseModel):
    id: int
    dns_authenticator_update: DNSAuthenticatorUpdate


class DNSAuthenticatorDeleteArgs(BaseModel):
    id: int


class DNSAuthenticatorSchemasArgs(BaseModel):
    pass


###################   Returns   ###################


class ACMERegistrationCreateResult(BaseModel):
    result: ACMERegistrationEntry


class DNSAuthenticatorCreateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class DNSAuthenticatorUpdateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class DNSAuthenticatorDeleteResult(BaseModel):
    result: bool


class DNSAuthenticatorSchemasResult(BaseModel):
    result: list[DNSAuthenticatorSchemaEntry]
