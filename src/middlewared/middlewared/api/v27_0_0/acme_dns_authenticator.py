from pathlib import Path
from typing import Annotated, Literal, TypeAlias

from pydantic import BeforeValidator, ConfigDict, Discriminator, Field, FilePath, PlainSerializer, Secret

from middlewared.api.base import (
    BaseModel, single_argument_args, ForUpdateMetaclass, NonEmptyString, OVHEndpoint,
)


__all__ = [
    'DNSAuthenticatorEntry', 'DNSAuthenticatorCreateArgs', 'DNSAuthenticatorCreateResult',
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
    result: dict = Field(description="Custom DNS authenticator schema configuration.")


class TrueNASConnectSchema(BaseModel):
    pass


@single_argument_args('attributes')
class TrueNASConnectSchemaArgs(TrueNASConnectSchema):
    pass


class CloudFlareSchema(BaseModel):
    authenticator: Literal['cloudflare'] = Field(description="DNS authenticator type identifier for Cloudflare.")
    cloudflare_email: NonEmptyString | None = Field(default=None, description="Cloudflare Email.")
    api_key: Secret[NonEmptyString | None] = Field(default=None, description="API Key.")
    api_token: Secret[NonEmptyString | None] = Field(default=None, description="API Token.")


@single_argument_args('attributes')
class CloudFlareSchemaArgs(CloudFlareSchema):
    pass


class DigitalOceanSchema(BaseModel):
    authenticator: Literal['digitalocean'] = Field(description="DNS authenticator type identifier for DigitalOcean.")
    digitalocean_token: Secret[NonEmptyString] = Field(description="DigitalOcean Token.")


@single_argument_args('attributes')
class DigitalOceanSchemaArgs(DigitalOceanSchema):
    pass


class OVHSchema(BaseModel):
    authenticator: Literal['OVH'] = Field(description="DNS authenticator type identifier for OVH.")
    application_key: NonEmptyString = Field(description="OVH Application Key.")
    application_secret: NonEmptyString = Field(description="OVH Application Secret.")
    consumer_key: NonEmptyString = Field(description="OVH Consumer Key.")
    endpoint: OVHEndpoint = Field(description="OVH Endpoint.")


@single_argument_args('attributes')
class OVHSchemaArgs(OVHSchema):
    pass


class Route53Schema(BaseModel):
    authenticator: Literal['route53'] = Field(description="DNS authenticator type identifier for AWS Route 53.")
    access_key_id: NonEmptyString = Field(description="AWS Access Key ID.")
    secret_access_key: NonEmptyString = Field(description="AWS Secret Access Key.")


@single_argument_args('attributes')
class Route53SchemaArgs(Route53Schema):
    pass


class ShellSchema(BaseModel):
    authenticator: Literal['shell'] = Field(description="DNS authenticator type identifier for custom shell scripts.")
    script: FilePathStr = Field(description="Authentication Script.")
    user: NonEmptyString = Field(default='nobody', description="Running user.")
    timeout: int = Field(ge=5, default=60, description="Script Timeout.")
    delay: int = Field(ge=10, default=60, description="Propagation delay.")


@single_argument_args('attributes')
class ShellSchemaArgs(ShellSchema):
    pass


AuthType: TypeAlias = Annotated[
    CloudFlareSchema | DigitalOceanSchema | OVHSchema | Route53Schema | ShellSchema,
    Discriminator('authenticator')
]


# ACME DNS Authenticator


class DNSAuthenticatorEntry(BaseModel):
    id: int = Field(description="Unique identifier for the DNS authenticator.")
    attributes: Secret[AuthType] = Field(
        description="Authentication credentials and configuration (masked for security).",
    )
    name: str = Field(description="Human-readable name for the DNS authenticator.")


class ACMEDNSAuthenticatorCreate(BaseModel):
    attributes: AuthType = Field(description="Authentication credentials and configuration for the DNS provider.")
    name: str = Field(description="Human-readable name for the DNS authenticator.")


@single_argument_args('dns_authenticator_create')
class DNSAuthenticatorCreateArgs(ACMEDNSAuthenticatorCreate):
    pass


class DNSAuthenticatorCreateResult(BaseModel):
    result: DNSAuthenticatorEntry = Field(description="The created DNS authenticator configuration.")


class ACMEDNSAuthenticatorUpdate(ACMEDNSAuthenticatorCreate, metaclass=ForUpdateMetaclass):
    pass


class DNSAuthenticatorUpdateArgs(BaseModel):
    id: int = Field(description="ID of the DNS authenticator to update.")
    dns_authenticator_update: ACMEDNSAuthenticatorUpdate = Field(
        description="Updated DNS authenticator configuration data.",
    )


class DNSAuthenticatorUpdateResult(BaseModel):
    result: DNSAuthenticatorEntry = Field(description="The updated DNS authenticator configuration.")


class DNSAuthenticatorDeleteArgs(BaseModel):
    id: int = Field(description="ID of the DNS authenticator to delete.")


class DNSAuthenticatorDeleteResult(BaseModel):
    result: bool = Field(description="Returns `true` when the DNS authenticator is successfully deleted.")


class ACMEDNSAuthenticatorAttributeSchema(BaseModel):
    name: str = Field(alias='_name_', description="Internal name of the schema attribute.")
    title: str = Field(description="Human-readable title for the schema attribute.")
    required: bool = Field(alias='_required_', description="Whether this attribute is required for the authenticator.")

    model_config = ConfigDict(extra='allow')


class ACMEDNSAuthenticatorSchema(BaseModel):
    key: str = Field(description="Unique identifier for the DNS authenticator type.")
    schema_: ACMEDNSAuthenticatorAttributeSchema = Field(
        alias='schema',
        description="Schema definition for the authenticator's required attributes.",
    )


class DNSAuthenticatorAuthenticatorSchemasArgs(BaseModel):
    pass


class DNSAuthenticatorAuthenticatorSchemasResult(BaseModel):
    result: list[ACMEDNSAuthenticatorSchema] = Field(
        description="Available DNS authenticator schemas with their configuration requirements.",
    )
