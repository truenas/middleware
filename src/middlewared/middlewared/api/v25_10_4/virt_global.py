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
    """Unique identifier for the virtualization global configuration."""
    pool: str | None = None
    """Default storage pool when creating new instances and volumes."""
    dataset: str | None = None
    """ZFS dataset path used for virtualization data storage. `null` if not configured."""
    storage_pools: list[str] | None = None
    """ZFS pools to use as storage pools."""
    bridge: str | None = None
    """Network bridge interface for virtualized instance networking. `null` if not configured."""
    v4_network: str | None = None
    """IPv4 network CIDR for the virtualization bridge network. `null` if not configured."""
    v6_network: str | None = None
    """IPv6 network CIDR for the virtualization bridge network. `null` if not configured."""
    state: Literal['INITIALIZING', 'INITIALIZED', 'NO_POOL', 'ERROR', 'LOCKED'] | None = None
    """Current operational state of the virtualization subsystem. `null` during initial setup."""


class VirtGlobalUpdateResult(BaseModel):
    result: VirtGlobalEntry
    """The updated virtualization global configuration."""


@single_argument_args('virt_global_update')
class VirtGlobalUpdateArgs(BaseModel, metaclass=ForUpdateMetaclass):
    pool: NonEmptyString | None = None
    """Default storage pool when creating new instances and volumes."""
    bridge: NonEmptyString | None = None
    """Network bridge interface for virtualized instance networking. `null` to disable."""
    storage_pools: list[str] | None = None
    """ZFS pools to use as storage pools."""
    v4_network: str | None = None
    """IPv4 network CIDR for the virtualization bridge network. `null` to use default."""
    v6_network: str | None = None
    """IPv6 network CIDR for the virtualization bridge network. `null` to use default."""


class VirtGlobalBridgeChoicesArgs(BaseModel):
    pass


class VirtGlobalBridgeChoicesResult(BaseModel):
    result: dict
    """Object of available network bridge interfaces and their configurations."""


class VirtGlobalPoolChoicesArgs(BaseModel):
    pass


class VirtGlobalPoolChoicesResult(BaseModel):
    result: dict
    """Object of available ZFS pools that can be used for virtualization storage."""


class VirtGlobalGetNetworkArgs(BaseModel):
    name: NonEmptyString
    """Name of the network configuration to retrieve."""


@single_argument_result
class VirtGlobalGetNetworkResult(BaseModel):
    type: Literal['BRIDGE']
    """Type of network configuration (currently only bridge networks are supported)."""
    managed: bool
    """Whether this network is managed by the virtualization system."""
    ipv4_address: NonEmptyString
    """IPv4 address and CIDR of the bridge network."""
    ipv4_nat: bool
    """Whether IPv4 Network Address Translation is enabled for this bridge."""
    ipv6_address: NonEmptyString
    """IPv6 address and CIDR of the bridge network."""
    ipv6_nat: bool
    """Whether IPv6 Network Address Translation is enabled for this bridge."""
