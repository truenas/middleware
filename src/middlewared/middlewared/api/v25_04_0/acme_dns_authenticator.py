from typing import Literal

from lexicon.providers.ovh import ENDPOINTS
from pydantic import ConfigDict, conint, Field, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, single_argument_args, ForUpdateMetaclass, LongString, NonEmptyString,
)
from middlewared.api.base.types import FilePath


__all__ = [
    'ACMEDNSAuthenticatorEntry', 'ACMEDNSAuthenticatorCreateArgs', 'ACMEDNSAuthenticatorCreateResult',
    'ACMEDNSAuthenticatorUpdateArgs', 'ACMEDNSAuthenticatorUpdateResult', 'ACMEDNSAuthenticatorDeleteArgs',
    'ACMEDNSAuthenticatorDeleteResult', 'ACMEDNSAuthenticatorSchemasArgs', 'ACMEDNSAuthenticatorSchemasResult',
    'ACMEDNSAuthenticatorPerformChallengeArgs', 'ACMEDNSAuthenticatorPerformChallengeResult', 'Route53SchemaArgs',
    'ACMECustomDNSAuthenticatorReturns', 'CloudFlareSchemaArgs', 'OVHSchemaArgs', 'ShellSchemaArgs',
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
    id: int
    dns_authenticator_update: ACMEDNSAuthenticatorUpdate


class ACMEDNSAuthenticatorUpdateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class ACMEDNSAuthenticatorDeleteArgs(BaseModel):
    id: int


class ACMEDNSAuthenticatorDeleteResult(BaseModel):
    result: bool


@single_argument_args('acme_dns_authenticator_performance_challenge')
class ACMEDNSAuthenticatorPerformChallengeArgs(BaseModel):
    authenticator: int
    key: LongString
    domain: str
    challenge: LongString


class ACMEDNSAuthenticatorPerformChallengeResult(BaseModel):
    result: None


### Custom ACME DNS Authenticator Schemas


class ACMECustomDNSAuthenticatorReturns(BaseModel):
    result: dict


@single_argument_args('cloudflare')
class CloudFlareSchemaArgs(BaseModel):
    cloudflare_email: NonEmptyString = Field(..., description='Cloudflare Email')
    api_key: Secret[NonEmptyString] = Field(..., description='API Key')
    api_token: Secret[NonEmptyString] = Field(..., description='API Token')


@single_argument_args('ovh')
class OVHSchemaArgs(BaseModel):
    application_key: NonEmptyString = Field(..., description='OVH Application Key')
    application_secret: NonEmptyString = Field(..., description='OVH Application Secret')
    consumer_key: NonEmptyString = Field(..., description='OVH Consumer Key')
    endpoint: Literal[tuple(ENDPOINTS.keys())] = Field(..., description='OVH Endpoint')


@single_argument_args('route53')
class Route53SchemaArgs(BaseModel):
    access_key_id: NonEmptyString = Field(..., description='AWS Access Key ID')
    secret_access_key: NonEmptyString = Field(..., description='AWS Secret Access Key')


@single_argument_args('shell')
class ShellSchemaArgs(BaseModel):
    script: FilePath = Field(..., description='Authentication Script')
    user: NonEmptyString = Field(description='Running user', default='nobody')
    timeout: conint(ge=5) = Field(description='Script Timeout', default=60)
    delay: conint(ge=10) = Field(description='Propagation delay', default=60)


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
