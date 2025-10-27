from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from pydantic import BeforeValidator, ConfigDict, Field, FilePath, PlainSerializer, Secret

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, NonEmptyString, OVHEndpoint,
)


__all__ = [
    'ACMEDNSAuthenticatorEntry', 'DNSAuthenticatorCreateArgs', 'DNSAuthenticatorCreateResult',
    'DNSAuthenticatorUpdateArgs', 'DNSAuthenticatorUpdateResult', 'DNSAuthenticatorDeleteArgs',
    'DNSAuthenticatorDeleteResult', 'DNSAuthenticatorAuthenticatorSchemasArgs',
    'DNSAuthenticatorAuthenticatorSchemasResult', 'Route53SchemaArgs', 'ACMECustomDNSAuthenticatorReturns',
    'CloudFlareSchemaArgs', 'DigitalOceanSchemaArgs', 'OVHSchemaArgs', 'ShellSchemaArgs', 'TrueNASConnectSchemaArgs',
]


FilePathStr = Annotated[
    FilePath,
    BeforeValidator(lambda v: Path(v) if isinstance(v, str) else v),
    PlainSerializer(lambda x: str(x)),
]


# Custom ACME DNS Authenticator Schemas


class ACMECustomDNSAuthenticatorReturns(BaseModel):
    result: dict
    """Custom DNS authenticator schema configuration."""


class TrueNASConnectSchema(BaseModel):
    pass


@single_argument_args('attributes')
class TrueNASConnectSchemaArgs(TrueNASConnectSchema):
    pass


class CloudFlareSchema(BaseModel):
    authenticator: Literal['cloudflare']
    """DNS authenticator type identifier for Cloudflare."""
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
    """DNS authenticator type identifier for DigitalOcean."""
    digitalocean_token: Secret[NonEmptyString]
    """DigitalOcean Token."""


@single_argument_args('attributes')
class DigitalOceanSchemaArgs(DigitalOceanSchema):
    pass


class OVHSchema(BaseModel):
    authenticator: Literal['OVH']
    """DNS authenticator type identifier for OVH."""
    application_key: NonEmptyString
    """OVH Application Key."""
    application_secret: NonEmptyString
    """OVH Application Secret."""
    consumer_key: NonEmptyString
    """OVH Consumer Key."""
    endpoint: OVHEndpoint
    """OVH Endpoint."""


@single_argument_args('attributes')
class OVHSchemaArgs(OVHSchema):
    pass


class Route53Schema(BaseModel):
    authenticator: Literal['route53']
    """DNS authenticator type identifier for AWS Route 53."""
    access_key_id: NonEmptyString
    """AWS Access Key ID."""
    secret_access_key: NonEmptyString
    """AWS Secret Access Key."""


@single_argument_args('attributes')
class Route53SchemaArgs(Route53Schema):
    pass


class ShellSchema(BaseModel):
    authenticator: Literal['shell']
    """DNS authenticator type identifier for custom shell scripts."""
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
    """Unique identifier for the DNS authenticator."""
    attributes: Secret[AuthType]
    """Authentication credentials and configuration (masked for security)."""
    name: str
    """Human-readable name for the DNS authenticator."""


class ACMEDNSAuthenticatorCreate(BaseModel):
    attributes: AuthType
    """Authentication credentials and configuration for the DNS provider."""
    name: str
    """Human-readable name for the DNS authenticator."""


@single_argument_args('dns_authenticator_create')
class DNSAuthenticatorCreateArgs(ACMEDNSAuthenticatorCreate):
    pass


class DNSAuthenticatorCreateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry
    """The created DNS authenticator configuration."""


class ACMEDNSAuthenticatorUpdate(ACMEDNSAuthenticatorCreate, metaclass=ForUpdateMetaclass):
    pass


class DNSAuthenticatorUpdateArgs(BaseModel):
    id: int
    """ID of the DNS authenticator to update."""
    dns_authenticator_update: ACMEDNSAuthenticatorUpdate
    """Updated DNS authenticator configuration data."""


class DNSAuthenticatorUpdateResult(BaseModel):
    result: ACMEDNSAuthenticatorEntry
    """The updated DNS authenticator configuration."""


class DNSAuthenticatorDeleteArgs(BaseModel):
    id: int
    """ID of the DNS authenticator to delete."""


class DNSAuthenticatorDeleteResult(BaseModel):
    result: bool
    """Returns `true` when the DNS authenticator is successfully deleted."""


class ACMEDNSAuthenticatorAttributeSchema(BaseModel):
    name: str = Field(alias='_name_')
    """Internal name of the schema attribute."""
    title: str
    """Human-readable title for the schema attribute."""
    required: bool = Field(alias='_required_')
    """Whether this attribute is required for the authenticator."""

    model_config = ConfigDict(extra='allow')


class ACMEDNSAuthenticatorSchema(BaseModel):
    key: str
    """Unique identifier for the DNS authenticator type."""
    schema_: ACMEDNSAuthenticatorAttributeSchema = Field(alias='schema')
    """Schema definition for the authenticator's required attributes."""


class DNSAuthenticatorAuthenticatorSchemasArgs(BaseModel):
    pass


class DNSAuthenticatorAuthenticatorSchemasResult(BaseModel):
    result: list[ACMEDNSAuthenticatorSchema]
    """Available DNS authenticator schemas with their configuration requirements."""
