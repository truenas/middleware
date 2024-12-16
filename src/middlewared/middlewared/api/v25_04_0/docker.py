from typing import Annotated, Literal

from pydantic import IPvAnyInterface, Field, field_validator, model_validator

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)


class AddressPool(BaseModel):
    base: IPvAnyInterface
    size: Annotated[int, Field(ge=1)]

    @field_validator('base')
    @classmethod
    def check_prefixlen(cls, v):
        if v.network.prefixlen in (32, 128):
            raise ValueError('Prefix length of base network cannot be 32 or 128.')
        return v

    @model_validator(mode='after')
    def validate_attrs(self):
        if self.base.version == 4 and self.size > 32:
            raise ValueError('Size must be <= 32 for IPv4.')
        elif self.base.version == 6 and self.size > 128:
                raise ValueError('Size must be <= 128 for IPv6.')
        return self


class DockerEntry(BaseModel):
    id: int
    enable_image_updates: bool
    dataset: NonEmptyString | None
    pool: NonEmptyString | None
    nvidia: bool
    address_pools: list[dict]
    cidr_v6: str


@single_argument_args('docker_update')
class DockerUpdateArgs(DockerEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()
    address_pools: list[AddressPool]
    cidr_v6: IPvAnyInterface

    @field_validator('cidr_v6')
    @classmethod
    def validate_ipv6(cls, v):
        if v.version != 6:
            raise ValueError('cidr_v6 must be an IPv6 address.')
        if v.network.prefixlen == 128:
            raise ValueError('Prefix length of cidr_v6 network cannot be 128.')
        return v


class DockerUpdateResult(BaseModel):
    result: DockerEntry


class DockerStatusArgs(BaseModel):
    pass


class StatusResult(BaseModel):
    description: str
    status: Literal['PENDING', 'RUNNING', 'STOPPED', 'INITIALIZING', 'STOPPING', 'UNCONFIGURED', 'FAILED']


class DockerStatusResult(BaseModel):
    result: StatusResult


class DockerNvidiaPresentArgs(BaseModel):
    pass


class DockerNvidiaPresentResult(BaseModel):
    result: bool
