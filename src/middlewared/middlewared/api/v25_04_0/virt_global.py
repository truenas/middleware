from typing import Literal

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, NonEmptyString, single_argument_args, single_argument_result,
)


__all__ = [
    'VirtGlobalEntry', 'VirtGlobalUpdateResult', 'VirtGlobalUpdateArgs', 'VirtGlobalBridgeChoicesArgs',
    'VirtGlobalBridgeChoicesResult', 'VirtGlobalPoolChoicesArgs', 'VirtGlobalPoolChoicesResult',
    'VirtGlobalGetNetworkArgs', 'VirtGlobalGetNetworkResult',
]


class VirtGlobalEntry(BaseModel):
    id: int
    pool: str | None = None
    dataset: str | None = None
    bridge: str | None = None
    v4_network: str | None = None
    v6_network: str | None = None
    state: Literal['INITIALIZING', 'INITIALIZED', 'NO_POOL', 'ERROR', 'LOCKED'] | None = None


class VirtGlobalUpdateResult(BaseModel):
    result: VirtGlobalEntry


@single_argument_args('virt_global_update')
class VirtGlobalUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    pool: NonEmptyString | None = None
    bridge: NonEmptyString | None = None
    v4_network: str | None = None
    v6_network: str | None = None


class VirtGlobalBridgeChoicesArgs(BaseModel):
    pass


class VirtGlobalBridgeChoicesResult(BaseModel):
    result: dict


class VirtGlobalPoolChoicesArgs(BaseModel):
    pass


class VirtGlobalPoolChoicesResult(BaseModel):
    result: dict


class VirtGlobalGetNetworkArgs(BaseModel):
    name: NonEmptyString


@single_argument_result
class VirtGlobalGetNetworkResult(BaseModel):
    type: Literal['BRIDGE']
    managed: bool
    ipv4_address: NonEmptyString
    ipv4_nat: bool
    ipv6_address: NonEmptyString
    ipv6_nat: bool
