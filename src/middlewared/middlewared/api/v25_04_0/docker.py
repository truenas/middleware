import typing

from pydantic import conint, IPvAnyInterface

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)
from middlewared.plugins.docker.state_utils import Status


class AddressPool(BaseModel):
    base: IPvAnyInterface
    size: conint(ge=1, le=32)


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
    status: typing.Literal[tuple(e.value for e in Status)]


class DockerStatusResult(BaseModel):
    result: StatusResult


class LacksNvidiaDriverArgs(BaseModel):
    pass


class LacksNvidiaDriverResult(BaseModel):
    result: bool
