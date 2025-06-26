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
    "InterfaceIpInUseArgs", "InterfaceIpInUseResult", "InterfaceLacpduRateChoicesArgs",
    "InterfaceLacpduRateChoicesResult", "InterfaceLagPortsChoicesArgs", "InterfaceLagPortsChoicesResult",
    "InterfaceRollbackArgs", "InterfaceRollbackResult", "InterfaceSaveDefaultRouteArgs",
    "InterfaceSaveDefaultRouteResult", "InterfaceServicesRestartedOnSyncArgs",
    "InterfaceServicesRestartedOnSyncResult", "InterfaceUpdateArgs", "InterfaceUpdateResult",
    "InterfaceVlanParentInterfaceChoicesArgs", "InterfaceVlanParentInterfaceChoicesResult",
    "InterfaceWebsocketInterfaceArgs", "InterfaceWebsocketInterfaceResult", "InterfaceWebsocketLocalIpArgs",
    "InterfaceWebsocketLocalIpResult", "InterfaceXmitHashPolicyChoicesArgs", "InterfaceXmitHashPolicyChoicesResult",
]


class InterfaceEntryAlias(BaseModel):
    type: str
    address: str
    netmask: str | int


class InterfaceEntryStateAlias(InterfaceEntryAlias):
    netmask: str | int = NotRequired
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
    rx_queues: int = NotRequired
    tx_queues: int = NotRequired
    aliases: list[InterfaceEntryStateAlias]
    vrrp_config: list | None = []
    # lagg section
    protocol: str | None = NotRequired
    ports: list[InterfaceEntryStatePort] = []
    xmit_hash_policy: str | None = None
    lacpdu_rate: str | None = None
    # vlan section
    parent: str | None = NotRequired
    tag: int | None = NotRequired
    pcp: int | None = NotRequired


class InterfaceEntry(BaseModel):
    id: str
    name: str
    fake: bool
    type: str
    state: InterfaceEntryState
    aliases: list[InterfaceEntryAlias]
    ipv4_dhcp: bool
    ipv6_auto: bool
    description: str
    mtu: int | None
    vlan_parent_interface: str | None = NotRequired
    vlan_tag: int | None = NotRequired
    vlan_pcp: int | None = NotRequired
    lag_protocol: str = NotRequired
    lag_ports: list[str] = []
    bridge_members: list[str] = []  # FIXME: Please document fields for HA Hardware
    enable_learning: bool = NotRequired

    class Config:
        extra = "allow"


class InterfaceChoicesOptions(BaseModel):
    bridge_members: bool = False
    """Include BRIDGE members."""
    lag_ports: bool = False
    """Include LINK_AGGREGATION ports."""
    vlan_parent: bool = True
    """Include VLAN parent interface."""
    exclude: list = ["epair", "tap", "vnet"]
    """Prefixes of interfaces to exclude from the result."""
    exclude_types: list[Literal["BRIDGE", "LINK_AGGREGATION", "PHYSICAL", "UNKNOWN", "VLAN"]] = []
    include: list[str] = []
    """Interfaces that should not be excluded."""


class InterfaceCommitOptions(BaseModel):
    rollback: bool = True
    """Roll back changes in case they fail to apply."""
    checkin_timeout: int = 60
    """Number of seconds to wait for the checkin call to acknowledge the interface changes happened as planned from \
    the user. If checkin does not happen within this period of time, the changes will get reverted."""


class InterfaceCreateFailoverAlias(BaseModel):
    type: Literal["INET", "INET6"] = "INET"
    address: IPvAnyAddress


class InterfaceCreateAlias(InterfaceCreateFailoverAlias):
    netmask: int


class InterfaceCreate(BaseModel):
    name: str = NotRequired
    """Generate a name if not provided based on `type`, e.g. "br0", "bond1", "vlan0"."""
    description: str = ""
    type: Literal["BRIDGE", "LINK_AGGREGATION", "VLAN"]
    ipv4_dhcp: bool = False
    ipv6_auto: bool = False
    aliases: UniqueList[InterfaceCreateAlias] = []
    failover_critical: bool = False
    failover_group: int | None = NotRequired
    failover_vhid: Annotated[int, Field(ge=1, le=255)] | None = NotRequired
    failover_aliases: list[InterfaceCreateFailoverAlias] = []
    failover_virtual_aliases: list[InterfaceCreateFailoverAlias] = []
    bridge_members: list = []
    enable_learning: bool = True
    stp: bool = True
    lag_protocol: Literal["LACP", "FAILOVER", "LOADBALANCE", "ROUNDROBIN", "NONE"] = NotRequired
    xmit_hash_policy: Literal["LAYER2", "LAYER2+3", "LAYER3+4", None] = None
    lacpdu_rate: Literal["SLOW", "FAST", None] = None
    lag_ports: list[str] = []
    vlan_parent_interface: str = NotRequired
    vlan_tag: int = Field(ge=1, le=4094, default=NotRequired)
    vlan_pcp: Annotated[int, Field(ge=0, le=7)] | None = NotRequired
    mtu: Annotated[int, Field(ge=68, le=9216)] | None = None


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


class InterfaceIPInUseItem(BaseModel):
    type: str
    address: IPvAnyAddress
    netmask: int
    broadcast: str = NotRequired


class InterfaceServicesRestartedOnSyncItem(BaseModel):
    type: str
    service: str
    ips: list[str]


class InterfaceUpdate(InterfaceCreate, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


# -------------------   Args and Results   ------------------- #


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
    data: InterfaceCreate


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


class InterfaceIpInUseArgs(BaseModel):
    options: InterfaceIPInUseOptions = Field(default_factory=InterfaceIPInUseOptions)


class InterfaceIpInUseResult(BaseModel):
    result: list[InterfaceIPInUseItem] = Field(examples=[[
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


class InterfaceServicesRestartedOnSyncArgs(BaseModel):
    pass


class InterfaceServicesRestartedOnSyncResult(BaseModel):
    result: list[InterfaceServicesRestartedOnSyncItem]


class InterfaceUpdateArgs(BaseModel):
    id: str
    data: InterfaceUpdate


class InterfaceUpdateResult(BaseModel):
    result: InterfaceEntry


class InterfaceVlanParentInterfaceChoicesArgs(BaseModel):
    pass


class InterfaceVlanParentInterfaceChoicesResult(BaseModel):
    result: dict[str, str]
    """Names and descriptions of available interfaces for `vlan_parent_interface` attribute."""


class InterfaceWebsocketInterfaceArgs(BaseModel):
    pass


class InterfaceWebsocketInterfaceResult(BaseModel):
    result: InterfaceEntry | None


class InterfaceWebsocketLocalIpArgs(BaseModel):
    pass


class InterfaceWebsocketLocalIpResult(BaseModel):
    result: IPvAnyAddress | None
    """The local IP address for the current websocket session or `null`."""


class InterfaceXmitHashPolicyChoicesArgs(BaseModel):
    pass


@single_argument_result
class InterfaceXmitHashPolicyChoicesResult(BaseModel):
    LAYER2: Literal["LAYER2"]
    LAYER2_3: Literal["LAYER2+3"] = Field(alias="LAYER2+3")
    LAYER3_4: Literal["LAYER3+4"] = Field(alias="LAYER3+4")
