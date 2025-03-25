from abc import ABC
from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, IPv4Address, UniqueList, IPvAnyAddress, Excluded, excluded_field, ForUpdateMetaclass,
    single_argument_result, NotRequired
)


__all__ = [
    "InterfaceEntry", "InterfaceBridgeMembersChoicesArgs", "InterfaceBridgeMembersChoicesResult",
    "InterfaceCancelRollbackArgs", "InterfaceCancelRollbackResult", "InterfaceCheckinArgs", "InterfaceCheckinResult",
    "InterfaceCheckinWaitingArgs", "InterfaceCheckinWaitingResult", "InterfaceChoicesArgs", "InterfaceChoicesResult",
    "InterfaceCommitArgs", "InterfaceCommitResult", "InterfaceCreateArgs", "InterfaceCreateResult",
    "InterfaceDefaultRouteWillBeRemovedArgs", "InterfaceDefaultRouteWillBeRemovedResult", "InterfaceDeleteArgs",
    "InterfaceDeleteResult", "InterfaceHasPendingChangesArgs", "InterfaceHasPendingChangesResult",
    "InterfaceIPInUseArgs", "InterfaceIPInUseResult", "InterfaceLacpduRateChoicesArgs",
    "InterfaceLacpduRateChoicesResult", "InterfaceLagPortsChoicesArgs", "InterfaceLagPortsChoicesResult",
    "InterfaceRollbackArgs", "InterfaceRollbackResult", "InterfaceSaveDefaultRouteArgs",
    "InterfaceSaveDefaultRouteResult", "InterfaceUpdateArgs", "InterfaceUpdateResult",
    "InterfaceVLANParentInterfaceChoicesArgs", "InterfaceVLANParentInterfaceChoicesResult",
    "InterfaceWebsocketInterfaceArgs", "InterfaceWebsocketInterfaceResult", "InterfaceWebsocketLocalIPArgs",
    "InterfaceWebsocketLocalIPResult", "InterfaceXmitHashPolicyChoicesArgs", "InterfaceXmitHashPolicyChoicesResult",
]


class InterfaceFailoverAlias(BaseModel):
    type: Literal["INET", "INET6"] = "INET"
    address: IPvAnyAddress


class InterfaceAlias(InterfaceFailoverAlias):
    netmask: int


class InterfaceEntryStateAlias(InterfaceAlias):
    broadcast: str = NotRequired


class InterfaceEntryStatePort(BaseModel):
    name: str
    flags: list[str]


class InterfaceEntryState(BaseModel):
    name: str
    orig_name: str
    description: str
    mtu: int
    cloned: bool
    flags: list[str]
    nd6_flags: list
    capabilities: list
    link_state: str
    media_type: str
    media_subtype: str
    active_media_type: str
    active_media_subtype: str
    supported_media: list
    media_options: list | None
    link_address: str
    permanent_link_address: str | None
    hardware_link_address: str
    rx_queues: int
    tx_queues: int
    aliases: list[InterfaceEntryStateAlias]
    vrrp_config: list | None
    # lagg section
    protocol: str | None
    ports: list[InterfaceEntryStatePort]
    xmit_hash_policy: str | None = None
    lacpdu_rate: str | None = None
    # vlan section
    parent: str | None
    tag: int | None
    pcp: int | None


class InterfaceEntry(BaseModel):
    id: str
    name: str
    fake: bool
    type: str
    state: InterfaceEntryState
    aliases: list[InterfaceAlias]
    ipv4_dhcp: bool
    ipv6_auto: bool
    description: str
    mtu: int | None
    vlan_parent_interface: str | None
    vlan_tag: int | None
    vlan_pcp: int | None
    lag_protocol: str
    lag_ports: list[str]
    bridge_members: list[str]
    enable_learning: bool

    class Config:
        extra = "allow"


class InterfaceChoicesOptions(BaseModel):
    bridge_members: bool = False
    """Include BRIDGE members."""
    lag_ports: bool = False
    """Include LINK_AGGREGATION ports."""
    vlan_parent: bool = True
    """Include VLAN parent interface."""
    exclude: list[str] = ["epair", "tap", "vnet"]
    """Prefixes of interfaces to exclude from the result."""
    exclude_types: list[Literal["BRIDGE", "LINK_AGGREGATION", "PHYSICAL", "UNKNOWN", "VLAN"]] = []
    include: list[str] = []
    """Interfaces that should not be excluded."""


class InterfaceCommitOptions(BaseModel):
    rollback: bool = True
    """Roll back changes in case they fail to apply."""
    checkin_timeout: int = 60
    """Number of seconds to wait for the checkin call to acknowledge the interface changes happened as planned from the
    user. If checkin does not happen within this period of time, the changes will get reverted."""


class InterfaceCreate(BaseModel, ABC):
    name: str = None
    """Generate a name if not provided based on `type`, e.g. "br0", "bond1", "vlan0"."""
    description: str = ""
    ipv4_dhcp: bool = False
    ipv6_auto: bool = False
    aliases: UniqueList[InterfaceAlias] = []
    failover_critical: bool = False
    failover_group: int | None = None
    failover_vhid: Annotated[int, Field(ge=1, le=255)] | None = None
    failover_aliases: list[InterfaceFailoverAlias] = []
    failover_virtual_aliases: list[InterfaceFailoverAlias] = []
    mtu: Annotated[int, Field(ge=68, le=9216)] | None = None


class InterfaceCreateBridge(InterfaceCreate):
    type: Literal["BRIDGE"]
    bridge_members: list
    stp: bool = True
    enable_learning: bool = True


class InterfaceCreateLinkAggregation(InterfaceCreate):
    type: Literal["LINK_AGGREGATION"]
    lag_protocol: Literal["LACP", "FAILOVER", "LOADBALANCE", "ROUNDROBIN", "NONE"]
    lag_ports: list[str]
    xmit_hash_policy: Literal["LAYER2", "LAYER2+3", "LAYER3+4", None] = None
    """Default to "LAYER2+3" if `lag_protocol` is either "LACP" or "LOADBALANCE"."""
    lacpdu_rate: Literal["SLOW", "FAST", None] = None
    """Default to "SLOW" if `lag_protocol` is "LACP"."""


class InterfaceCreateVLAN(InterfaceCreate):
    type: Literal["VLAN"]
    vlan_parent_interface: str
    vlan_tag: int = Field(ge=1, le=4094)
    vlan_pcp: Annotated[int, Field(ge=0, le=7)] | None = None


class InterfaceIPInUseOptions(BaseModel):
    ipv4: bool = True
    ipv6: bool = True
    ipv6_link_local: bool = False
    loopback: bool = False
    """Return loopback interface addresses."""
    any: bool = False
    """Return wildcard addresses (0.0.0.0 and ::)."""
    static: bool = False
    """Only return configured static IPs."""


class InterfaceUpdateBridge(InterfaceCreateBridge, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


class InterfaceUpdateLinkAggregation(InterfaceCreateLinkAggregation, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


class InterfaceUpdateVLAN(InterfaceCreateVLAN, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


################   Args and Results   ###############


class InterfaceBridgeMembersChoicesArgs(BaseModel):
    id: str | None = None
    """Name of existing bridge interface whose member interfaces should be included in the result."""


class InterfaceBridgeMembersChoicesResult(BaseModel):
    result: dict[str, str]
    """IDs of available interfaces that can be added to a bridge interface."""


class InterfaceCancelRollbackArgs(BaseModel):
    pass


class InterfaceCancelRollbackResult(BaseModel):
    result: None


class InterfaceCheckinArgs(BaseModel):
    pass


class InterfaceCheckinResult(BaseModel):
    result: None


class InterfaceCheckinWaitingArgs(BaseModel):
    pass


class InterfaceCheckinWaitingResult(BaseModel):
    result: int | None
    """Number of seconds left to wait or `null` if not waiting."""


class InterfaceChoicesArgs(BaseModel):
    options: InterfaceChoicesOptions = Field(default_factory=InterfaceChoicesOptions)


class InterfaceChoicesResult(BaseModel):
    result: dict[str, str]
    """Names and descriptions of available network interfaces."""


class InterfaceCommitArgs(BaseModel):
    options: InterfaceCommitOptions = Field(default_factory=InterfaceCommitOptions)


class InterfaceCommitResult(BaseModel):
    result: None


class InterfaceCreateArgs(BaseModel):
    data: InterfaceCreateBridge | InterfaceCreateLinkAggregation | InterfaceCreateVLAN = Field(discriminator="type")


class InterfaceCreateResult(BaseModel):
    result: InterfaceEntry


class InterfaceDefaultRouteWillBeRemovedArgs(BaseModel):
    pass


class InterfaceDefaultRouteWillBeRemovedResult(BaseModel):
    result: bool


class InterfaceDeleteArgs(BaseModel):
    id: str
    """ID of the interface to delete."""


class InterfaceDeleteResult(BaseModel):
    result: str
    """ID of the interface that was deleted."""


class InterfaceHasPendingChangesArgs(BaseModel):
    pass


class InterfaceHasPendingChangesResult(BaseModel):
    result: bool


class InterfaceIPInUseArgs(BaseModel):
    options: InterfaceIPInUseOptions = Field(default_factory=InterfaceIPInUseOptions)


class InterfaceIPInUseResult(BaseModel):
    result: list[InterfaceEntryStateAlias] = Field(examples=[[
        {
            "type": "INET6",
            "address": "fe80::5054:ff:fe16:4aac",
            "netmask": 64
        },
        {
            "type": "INET",
            "address": "192.168.122.148",
            "netmask": 24,
            "broadcast": "192.168.122.255"
        },
    ]])


class InterfaceLacpduRateChoicesArgs(BaseModel):
    pass


@single_argument_result
class InterfaceLacpduRateChoicesResult(BaseModel):
    SLOW: Literal["SLOW"]
    FAST: Literal["FAST"]


class InterfaceLagPortsChoicesArgs(BaseModel):
    id: str | None = None
    """Name of existing bond interface whose member interfaces should be included in the result."""


class InterfaceLagPortsChoicesResult(BaseModel):
    result: dict[str, str]
    """IDs of available interfaces that can be added to a bond interface."""


class InterfaceRollbackArgs(BaseModel):
    pass


class InterfaceRollbackResult(BaseModel):
    result: None


class InterfaceSaveDefaultRouteArgs(BaseModel):
    gateway: IPv4Address


class InterfaceSaveDefaultRouteResult(BaseModel):
    result: None


class InterfaceUpdateArgs(BaseModel):
    id: str
    data: InterfaceUpdateBridge | InterfaceUpdateLinkAggregation | InterfaceUpdateVLAN


class InterfaceUpdateResult(BaseModel):
    result: InterfaceEntry


class InterfaceVLANParentInterfaceChoicesArgs(BaseModel):
    pass


class InterfaceVLANParentInterfaceChoicesResult(BaseModel):
    result: dict[str, str]
    """Names and descriptions of available interfaces for `vlan_parent_interface` attribute."""


class InterfaceWebsocketInterfaceArgs(BaseModel):
    pass


class InterfaceWebsocketInterfaceResult(BaseModel):
    result: InterfaceEntry | None


class InterfaceWebsocketLocalIPArgs(BaseModel):
    pass


class InterfaceWebsocketLocalIPResult(BaseModel):
    result: IPvAnyAddress | None
    """The local IP address for the current websocket session or `null`."""


class InterfaceXmitHashPolicyChoicesArgs(BaseModel):
    pass


@single_argument_result
class InterfaceXmitHashPolicyChoicesResult(BaseModel):
    LAYER2: Literal["LAYER2"]
    LAYER2_3: Literal["LAYER2+3"] = Field(alias="LAYER2+3")
    LAYER3_4: Literal["LAYER3+4"] = Field(alias="LAYER3+4")
