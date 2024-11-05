from pathlib import Path
from typing import Annotated, Literal

from lexicon.providers.ovh import ENDPOINTS
from pydantic import BeforeValidator, ConfigDict, conint, Field, FilePath, PlainSerializer, Secret

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, single_argument_args, ForUpdateMetaclass, LongString, NonEmptyString,
)


__all__ = [
    'ACMEDNSAuthenticatorEntry', 'ACMEDNSAuthenticatorCreateArgs', 'ACMEDNSAuthenticatorCreateResult',
    'ACMEDNSAuthenticatorUpdateArgs', 'ACMEDNSAuthenticatorUpdateResult', 'ACMEDNSAuthenticatorDeleteArgs',
    'ACMEDNSAuthenticatorDeleteResult', 'ACMEDNSAuthenticatorSchemasArgs', 'ACMEDNSAuthenticatorSchemasResult',
    'ACMEDNSAuthenticatorPerformChallengeArgs', 'ACMEDNSAuthenticatorPerformChallengeResult', 'Route53SchemaArgs',
    'ACMECustomDNSAuthenticatorReturns', 'CloudFlareSchemaArgs', 'OVHSchemaArgs', 'ShellSchemaArgs',
]


FilePathStr = Annotated[
    FilePath,
    BeforeValidator(lambda v: Path(v) if isinstance(v, str) else v),
    PlainSerializer(lambda x: str(x)),
]


### Custom ACME DNS Authenticator Schemas


class ACMECustomDNSAuthenticatorReturns(BaseModel):
    result: dict


class CloudFlareSchema(BaseModel):
    cloudflare_email: NonEmptyString | None = Field(default=None, description='Cloudflare Email')
    api_key: Secret[NonEmptyString | None] = Field(default=None, description='API Key')
    api_token: Secret[NonEmptyString | None] = Field(default=None, description='API Token')


@single_argument_args('attributes')
class CloudFlareSchemaArgs(CloudFlareSchema):
    pass


class OVHSchema(BaseModel):
    application_key: NonEmptyString = Field(..., description='OVH Application Key')
    application_secret: NonEmptyString = Field(..., description='OVH Application Secret')
    consumer_key: NonEmptyString = Field(..., description='OVH Consumer Key')
    endpoint: Literal[tuple(ENDPOINTS.keys())] = Field(..., description='OVH Endpoint')


@single_argument_args('attributes')
class OVHSchemaArgs(OVHSchema):
    pass


class Route53Schema(BaseModel):
    access_key_id: NonEmptyString = Field(..., description='AWS Access Key ID')
    secret_access_key: NonEmptyString = Field(..., description='AWS Secret Access Key')


@single_argument_args('attributes')
class Route53SchemaArgs(Route53Schema):
    pass


class ShellSchema(BaseModel):
    script: FilePathStr = Field(..., description='Authentication Script')
    user: NonEmptyString = Field(description='Running user', default='nobody')
    timeout: conint(ge=5) = Field(description='Script Timeout', default=60)
    delay: conint(ge=10) = Field(description='Propagation delay', default=60)


@single_argument_args('attributes')
class ShellSchemaArgs(ShellSchema):
    pass


## ACME DNS Authenticator


class ACMEDNSAuthenticatorEntry(BaseModel):
    id: int
    authenticator: str
    attributes: Secret[CloudFlareSchema | OVHSchema | Route53Schema | ShellSchema]
    name: str


@single_argument_args('dns_authenticator_create')
class ACMEDNSAuthenticatorCreateArgs(ACMEDNSAuthenticatorEntry):
    id: Excluded = excluded_field()
    attributes: dict


class ACMEDNSAuthenticatorCreateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class ACMEDNSAuthenticatorUpdate(ACMEDNSAuthenticatorEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    authenticator: Excluded = excluded_field()
    attributes: dict


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


class ACMEDNSAuthenticatorAttributeSchema(BaseModel):
    _name_: str
    title: str
    _required_: bool

    model_config = ConfigDict(extra='allow')


class ACMEDNSAuthenticatorSchema(BaseModel):
    key: str
    schema_: ACMEDNSAuthenticatorAttributeSchema = Field(..., alias='schema')


class ACMEDNSAuthenticatorSchemasArgs(BaseModel):
    pass


class ACMEDNSAuthenticatorSchemasResult(BaseModel):
    result: list[ACMEDNSAuthenticatorSchema]
