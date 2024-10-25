from pydantic import conint, IPvAnyNetwork

from middlewared.api.base import BaseModel, NonEmptyString


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
