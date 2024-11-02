from pydantic import ConfigDict, Field, Secret

from middlewared.api.base import BaseModel, Excluded, excluded_field, single_argument_args, ForUpdateMetaclass


__all__ = [
    'ACMEDNSAuthenticatorEntry', 'ACMEDNSAuthenticatorCreateArgs', 'ACMEDNSAuthenticatorCreateResult',
    'ACMEDNSAuthenticatorUpdateArgs', 'ACMEDNSAuthenticatorUpdateResult', 'ACMEDNSAuthenticatorDeleteArgs',
    'ACMEDNSAuthenticatorDeleteResult', 'ACMEDNSAuthenticatorSchemasArgs', 'ACMEDNSAuthenticatorSchemasResult',
]


class ACMEDNSAuthenticatorEntry(BaseModel):
    id: int
    authenticator: str
    attributes: Secret[dict]
    name: str


@single_argument_args('dns_authenticator_create')
class ACMEDNSAuthenticatorCreateArgs(ACMEDNSAuthenticatorEntry):
    id: Excluded = excluded_field()


class ACMEDNSAuthenticatorCreateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class ACMEDNSAuthenticatorUpdate(ACMEDNSAuthenticatorEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    authenticator: Excluded = excluded_field()


class ACMEDNSAuthenticatorUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    dns_authenticator_update: ACMEDNSAuthenticatorUpdate


class ACMEDNSAuthenticatorUpdateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class ACMEDNSAuthenticatorDeleteArgs(BaseModel):
    id: int


class ACMEDNSAuthenticatorDeleteResult(BaseModel):
    result: bool


### Custom ACME DNS Authenticator Schemas


class ACMEDNSAuthenticatorAttributeSchema(BaseModel):
    _name_: str
    title: str
    _required_: bool

    model_config = ConfigDict(extra='allow')  # FIXME: Remove this once we have proper schema


class ACMEDNSAuthenticatorSchema(BaseModel):
    key: str
    schema_: list[ACMEDNSAuthenticatorAttributeSchema] = Field(..., alias='schema')


class ACMEDNSAuthenticatorSchemasArgs(BaseModel):
    pass


class ACMEDNSAuthenticatorSchemasResult(BaseModel):
    result: list[ACMEDNSAuthenticatorSchema]
