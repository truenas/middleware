import typing

from pydantic import conint, IPvAnyInterface, field_validator

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)


class AddressPool(BaseModel):
    base: IPvAnyInterface
    size: conint(ge=1, le=32)

    @field_validator('base')
    def check_prefixlen(cls, v):
        if v.network.prefixlen in (32, 128):
            raise ValueError('Prefix length of base network cannot be 32 or 128.')
        return v


class DockerEntry(BaseModel):
    id: int
    enable_image_updates: bool
    dataset: NonEmptyString | None
    pool: NonEmptyString | None
    nvidia: bool
    address_pools: list[AddressPool]


@single_argument_args('docker_update')
class DockerUpdateArgs(DockerEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    dataset: Excluded = excluded_field()


class DockerUpdateResult(BaseModel):
    result: DockerEntry


class DockerStatusArgs(BaseModel):
    pass


class StatusResult(BaseModel):
    description: str
    status: typing.Literal['PENDING', 'RUNNING', 'STOPPED', 'INITIALIZING', 'STOPPING', 'UNCONFIGURED', 'FAILED']


class DockerStatusResult(BaseModel):
    result: StatusResult


class LacksNvidiaDriverArgs(BaseModel):
    pass


class LacksNvidiaDriverResult(BaseModel):
    result: bool
