from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IPv4Network, IPv6Network, single_argument_args,
)

__all__ = [
    "ContainerConfigEntry",
    "ContainerConfigUpdateArgs", "ContainerConfigUpdateResult",
    "ContainerConfigBridgeChoicesArgs", "ContainerConfigBridgeChoicesResult",
]


class ContainerConfigEntry(BaseModel):
    id: int
    """Configuration ID."""
    bridge: str | None = None
    """Network bridge interface for virtualized instance networking. `null` if not configured."""
    v4_network: IPv4Network | None = None
    """IPv4 network CIDR for the virtualization bridge network. `null` if not configured."""
    v6_network: IPv6Network | None = None
    """IPv6 network CIDR for the virtualization bridge network. `null` if not configured."""


@single_argument_args("container_config_update")
class ContainerConfigUpdateArgs(ContainerConfigEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class ContainerConfigUpdateResult(BaseModel):
    result: ContainerConfigEntry
    """Updated container configuration."""


class ContainerConfigBridgeChoicesArgs(BaseModel):
    pass


class ContainerConfigBridgeChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available network bridge interfaces and their configurations."""
