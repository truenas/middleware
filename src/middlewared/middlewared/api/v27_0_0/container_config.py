from pydantic import Field

from middlewared.api.base import (
    BaseModel, Excluded, excluded_field, ForUpdateMetaclass, IPv4Network, IPv6Network, single_argument_args,
)

__all__ = [
    "LXCConfigEntry",
    "LXCConfigUpdateArgs", "LXCConfigUpdateResult",
    "LXCConfigBridgeChoicesArgs", "LXCConfigBridgeChoicesResult",
]


class LXCConfigEntry(BaseModel):
    id: int = Field(description="Configuration ID.")
    preferred_pool: str | None = Field(default=None, description="Default pool used by containers and image datasets.")
    bridge: str | None = Field(
        default=None,
        description=(
            "Bridge that new container NICs attach to by default. `null` selects the automatically managed "
            "`truenasbr0` bridge, which provides DHCP, DNS and NAT for containers. Changing it does not move existing "
            "NICs."
        ),
    )
    v4_network: IPv4Network = Field(description="IPv4 network CIDR for the container bridge network.")
    v6_network: IPv6Network = Field(description="IPv6 network CIDR for the container bridge network.")


@single_argument_args("lxc_config_update")
class LXCConfigUpdateArgs(LXCConfigEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()


class LXCConfigUpdateResult(BaseModel):
    result: LXCConfigEntry = Field(description="Updated LXC configuration.")


class LXCConfigBridgeChoicesArgs(BaseModel):
    pass


class LXCConfigBridgeChoicesResult(BaseModel):
    result: dict[str, str] = Field(
        description="Object of available network bridge interfaces and their configurations.",
    )
