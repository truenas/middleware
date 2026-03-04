from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IPv4Network, IPv6Network, single_argument_args,
)

__all__ = [
    "LXCConfigEntry",
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


@single_argument_args("lxc_config_update")
class LXCConfigUpdateArgs(LXCConfigEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class LXCConfigUpdateResult(BaseModel):
    result: LXCConfigEntry
    """Updated LXC configuration."""


class LXCConfigBridgeChoicesArgs(BaseModel):
    pass


class LXCConfigBridgeChoicesResult(BaseModel):
    result: dict[str, str]
    """Object of available network bridge interfaces and their configurations."""
