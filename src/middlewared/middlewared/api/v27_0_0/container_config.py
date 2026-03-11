from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IPv4Network, IPv6Network,
)

__all__ = [
    "LXCConfigEntry", "LXCConfigUpdate",
    "LXCConfigUpdateArgs", "LXCConfigUpdateResult",
    "LXCConfigBridgeChoicesArgs", "LXCConfigBridgeChoicesResult",
]


class LXCConfigEntry(BaseModel):
    id: int
    """Configuration ID."""
    preferred_pool: str | None = None
    """Default pool used by containers and image datasets."""
    bridge: str | None = None
    """Network bridge interface for virtualized instance networking. `null` if not configured."""
    v4_network: IPv4Network
    """IPv4 network CIDR for the container bridge network."""
    v6_network: IPv6Network
    """IPv6 network CIDR for the container bridge network."""


class LXCConfigUpdate(LXCConfigEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class LXCConfigUpdateArgs(BaseModel):
    data: LXCConfigUpdate
    """LXC config update parameters."""


class LXCConfigUpdateResult(BaseModel):
    result: LXCConfigEntry
    """Updated LXC configuration."""


class LXCConfigBridgeChoicesArgs(BaseModel):
    pass


class LXCConfigBridgeChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available network bridge interfaces and their configurations."""
