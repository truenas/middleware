from pydantic import conint, IPvAnyNetwork

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, NonEmptyString, single_argument_args,
)

class AddressPool(BaseModel):
    base: IPvAnyNetwork
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
