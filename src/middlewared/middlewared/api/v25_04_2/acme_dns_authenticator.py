from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from pydantic import BeforeValidator, ConfigDict, Field, FilePath, PlainSerializer, Secret

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, NonEmptyString, OVHEndpoint,
)


__all__ = [
    'DNSAuthenticatorEntry', 'DNSAuthenticatorCreateArgs', 'DNSAuthenticatorCreateResult',
    'DNSAuthenticatorUpdateArgs', 'DNSAuthenticatorUpdateResult', 'DNSAuthenticatorDeleteArgs',
    'DNSAuthenticatorDeleteResult', 'DNSAuthenticatorAuthenticatorSchemasArgs', 'DNSAuthenticatorAuthenticatorSchemasResult',
    'Route53SchemaArgs', 'ACMECustomDNSAuthenticatorReturns', 'CloudFlareSchemaArgs', 'DigitalOceanSchemaArgs',
    'OVHSchemaArgs', 'ShellSchemaArgs', 'TrueNASConnectSchemaArgs',
]


FilePathStr = Annotated[
    FilePath,
    BeforeValidator(lambda v: Path(v) if isinstance(v, str) else v),
    PlainSerializer(lambda x: str(x)),
]


# Custom ACME DNS Authenticator Schemas


class ACMECustomDNSAuthenticatorReturns(BaseModel):
    result: dict


class TrueNASConnectSchema(BaseModel):
    pass


@single_argument_args('attributes')
class TrueNASConnectSchemaArgs(TrueNASConnectSchema):
    pass


class CloudFlareSchema(BaseModel):
    authenticator: Literal['cloudflare']
    cloudflare_email: NonEmptyString | None = Field(default=None, description='Cloudflare Email')
    api_key: Secret[NonEmptyString | None] = Field(default=None, description='API Key')
    api_token: Secret[NonEmptyString | None] = Field(default=None, description='API Token')


@single_argument_args('attributes')
class CloudFlareSchemaArgs(CloudFlareSchema):
    pass


class DigitalOceanSchema(BaseModel):
    authenticator: Literal['digitalocean']
    digitalocean_token: Secret[NonEmptyString] = Field(description='DigitalOcean Token')


@single_argument_args('attributes')
class DigitalOceanSchemaArgs(DigitalOceanSchema):
    pass


class OVHSchema(BaseModel):
    authenticator: Literal['OVH']
    application_key: NonEmptyString = Field(description='OVH Application Key')
    application_secret: NonEmptyString = Field(description='OVH Application Secret')
    consumer_key: NonEmptyString = Field(description='OVH Consumer Key')
    endpoint: OVHEndpoint = Field(description='OVH Endpoint')


@single_argument_args('attributes')
class OVHSchemaArgs(OVHSchema):
    pass


class Route53Schema(BaseModel):
    authenticator: Literal['route53']
    access_key_id: NonEmptyString = Field(description='AWS Access Key ID')
    secret_access_key: NonEmptyString = Field(description='AWS Secret Access Key')


@single_argument_args('attributes')
class Route53SchemaArgs(Route53Schema):
    pass


class ShellSchema(BaseModel):
    authenticator: Literal['shell']
    script: FilePathStr = Field(description='Authentication Script')
    user: NonEmptyString = Field(description='Running user', default='nobody')
    timeout: Annotated[int, Field(ge=5, description='Script Timeout', default=60)]
    delay: Annotated[int, Field(ge=10, description='Propagation delay', default=60)]


@single_argument_args('attributes')
class ShellSchemaArgs(ShellSchema):
    pass


AuthType: TypeAlias = Annotated[
    CloudFlareSchema | DigitalOceanSchema | OVHSchema | Route53Schema | ShellSchema,
    Field(discriminator='authenticator')
]


# ACME DNS Authenticator


class DNSAuthenticatorEntry(BaseModel):
    id: int
    attributes: Secret[AuthType]
    name: str


class ACMEDNSAuthenticatorCreate(BaseModel):
    attributes: AuthType
    name: str


@single_argument_args('dns_authenticator_create')
class DNSAuthenticatorCreateArgs(ACMEDNSAuthenticatorCreate):
    pass


class DNSAuthenticatorCreateResult(BaseModel):
    result: DNSAuthenticatorEntry


class ACMEDNSAuthenticatorUpdate(ACMEDNSAuthenticatorCreate, metaclass=ForUpdateMetaclass):
    pass


class DNSAuthenticatorUpdateArgs(BaseModel):
    id: int
    dns_authenticator_update: ACMEDNSAuthenticatorUpdate


class DNSAuthenticatorUpdateResult(BaseModel):
    result: DNSAuthenticatorEntry


class DNSAuthenticatorDeleteArgs(BaseModel):
    id: int


class DNSAuthenticatorDeleteResult(BaseModel):
    result: bool


class ACMEDNSAuthenticatorAttributeSchema(BaseModel):
    _name_: str
    title: str
    _required_: bool

    model_config = ConfigDict(extra='allow')


class ACMEDNSAuthenticatorSchema(BaseModel):
    key: str
    schema_: ACMEDNSAuthenticatorAttributeSchema = Field(alias='schema')


class DNSAuthenticatorAuthenticatorSchemasArgs(BaseModel):
    pass


class DNSAuthenticatorAuthenticatorSchemasResult(BaseModel):
    result: list[ACMEDNSAuthenticatorSchema]
