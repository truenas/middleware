from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from lexicon.providers.ovh import ENDPOINTS
from pydantic import BeforeValidator, ConfigDict, Field, FilePath, PlainSerializer, Secret

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, NonEmptyString,
)


__all__ = [
    'ACMEDNSAuthenticatorEntry', 'DNSAuthenticatorCreateArgs', 'DNSAuthenticatorCreateResult',
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
    cloudflare_email: NonEmptyString | None = None
    """Cloudflare Email."""
    api_key: Secret[NonEmptyString | None] = None
    """API Key."""
    api_token: Secret[NonEmptyString | None] = None
    """API Token."""


@single_argument_args('attributes')
class CloudFlareSchemaArgs(CloudFlareSchema):
    pass


class DigitalOceanSchema(BaseModel):
    authenticator: Literal['digitalocean']
    digitalocean_token: Secret[NonEmptyString]
    """DigitalOcean Token."""


@single_argument_args('attributes')
class DigitalOceanSchemaArgs(DigitalOceanSchema):
    pass


class OVHSchema(BaseModel):
    authenticator: Literal['OVH']
    application_key: NonEmptyString
    """OVH Application Key."""
    application_secret: NonEmptyString
    """OVH Application Secret."""
    consumer_key: NonEmptyString
    """OVH Consumer Key."""
    endpoint: Literal[tuple(ENDPOINTS.keys())]
    """OVH Endpoint."""


@single_argument_args('attributes')
class OVHSchemaArgs(OVHSchema):
    pass


class Route53Schema(BaseModel):
    authenticator: Literal['route53']
    access_key_id: NonEmptyString
    """AWS Access Key ID."""
    secret_access_key: NonEmptyString
    """AWS Secret Access Key."""


@single_argument_args('attributes')
class Route53SchemaArgs(Route53Schema):
    pass


class ShellSchema(BaseModel):
    authenticator: Literal['shell']
    script: FilePathStr
    """Authentication Script."""
    user: NonEmptyString = 'nobody'
    """Running user."""
    timeout: int = Field(ge=5, default=60)
    """Script Timeout."""
    delay: int = Field(ge=10, default=60)
    """Propagation delay."""


@single_argument_args('attributes')
class ShellSchemaArgs(ShellSchema):
    pass


AuthType: TypeAlias = Annotated[
    CloudFlareSchema | DigitalOceanSchema | OVHSchema | Route53Schema | ShellSchema,
    Field(discriminator='authenticator')
]


# ACME DNS Authenticator


class ACMEDNSAuthenticatorEntry(BaseModel):
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
    result: ACMEDNSAuthenticatorEntry


class ACMEDNSAuthenticatorUpdate(ACMEDNSAuthenticatorCreate, metaclass=ForUpdateMetaclass):
    pass


class DNSAuthenticatorUpdateArgs(BaseModel):
    id: int
    dns_authenticator_update: ACMEDNSAuthenticatorUpdate


class DNSAuthenticatorUpdateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry


class DNSAuthenticatorDeleteArgs(BaseModel):
    id: int


class DNSAuthenticatorDeleteResult(BaseModel):
    result: bool


class ACMEDNSAuthenticatorAttributeSchema(BaseModel):
    name: str = Field(alias='_name_')
    title: str
    required: bool = Field(alias='_required_')

    model_config = ConfigDict(extra='allow')


class ACMEDNSAuthenticatorSchema(BaseModel):
    key: str
    schema_: ACMEDNSAuthenticatorAttributeSchema = Field(alias='schema')


class DNSAuthenticatorAuthenticatorSchemasArgs(BaseModel):
    pass


class DNSAuthenticatorAuthenticatorSchemasResult(BaseModel):
    result: list[ACMEDNSAuthenticatorSchema]
