from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, IPv4Address, UniqueList, IPvAnyAddress, Excluded, excluded_field, ForUpdateMetaclass,
    single_argument_result, NotRequired, NonEmptyString,
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
    """The type of IP address (INET for IPv4, INET6 for IPv6)."""
    address: str
    """The IP address value."""
    netmask: str | int
    """The network mask for the IP address, either as a string or CIDR notation integer."""


class InterfaceEntryStateAlias(InterfaceEntryAlias):
    netmask: str | int = NotRequired
    broadcast: str = NotRequired


class InterfaceEntryStatePort(BaseModel):
    name: str
    """The name of the port interface."""
    flags: list[str]
    """List of flags associated with the port."""


class InterfaceEntryState(BaseModel):
    name: str
    """Current name of the network interface."""
    orig_name: str
    """Original name of the network interface before any renaming."""
    description: str
    """Human-readable description of the network interface."""
    mtu: int
    """Maximum transmission unit size for the interface."""
    cloned: bool
    """Whether the interface is a cloned/virtual interface."""
    flags: list[str]
    """List of interface flags indicating various states and capabilities. Common flags include UP, DOWN, RUNNING, \
    MULTICAST, BROADCAST, LOOPBACK, and POINTOPOINT."""
    nd6_flags: list
    """IPv6 neighbor discovery flags. These control IPv6 autoconfiguration behavior and include flags like \
    AUTO_LINKLOCAL, ACCEPT_RTADV, and PERFORMNUD."""
    capabilities: list
    """List of hardware capabilities supported by the interface. Common capabilities include VLAN_MTU, JUMBO_MTU, \
    VLAN_HWTAGGING, VLAN_HWCSUM, and TSO4."""
    link_state: str
    """Current link state of the interface (up, down, etc.)."""
    media_type: str
    """Type of media/connection for the interface. Examples include Ethernet, 802.11, or loopback."""
    media_subtype: str
    """Subtype of media/connection for the interface. Examples include 1000baseT, 100baseTX, or autoselect."""
    active_media_type: str
    """Currently active media type. This may differ from configured media_type during autonegotiation."""
    active_media_subtype: str
    """Currently active media subtype. This reflects the actual negotiated connection speed and type."""
    supported_media: list
    """List of supported media types for the interface. Contains media descriptors like '1000baseT <full-duplex>' \
    or 'autoselect'."""
    media_options: list | None
    """Available media options for the interface. Options may include 'full-duplex', 'half-duplex', 'flowcontrol', \
    or 'rxpause'."""
    link_address: str
    """MAC address of the interface."""
    permanent_link_address: str | None
    """Permanent MAC address of the interface if different from current."""
    hardware_link_address: str
    """Hardware MAC address of the interface."""
    rx_queues: int = NotRequired
    """Number of receive queues configured for the interface."""
    tx_queues: int = NotRequired
    """Number of transmit queues configured for the interface."""
    aliases: list[InterfaceEntryStateAlias]
    """List of IP address aliases configured on the interface."""
    vrrp_config: list | None = []
    """VRRP (Virtual Router Redundancy Protocol) configuration for the interface."""
    # lagg section
    protocol: str | None = NotRequired
    """Link aggregation protocol used (LACP, FAILOVER, etc.)."""
    ports: list[InterfaceEntryStatePort] = []
    """List of ports that are members of this link aggregation group."""
    xmit_hash_policy: str | None = None
    """Transmit hash policy for load balancing in link aggregation. LAYER2 uses MAC addresses, LAYER2+3 adds IP \
    addresses, and LAYER3+4 includes TCP/UDP ports for distribution."""
    lacpdu_rate: str | None = None
    """LACP data unit transmission rate. SLOW sends LACPDUs every 30 seconds, FAST sends every 1 second for \
    quicker link failure detection."""
    # vlan section
    parent: str | None = NotRequired
    """Parent interface for VLAN configuration."""
    tag: int | None = NotRequired
    """VLAN tag number."""
    pcp: int | None = NotRequired
    """Priority Code Point for VLAN traffic prioritization. Values 0-7 map to different QoS priority levels, \
    with 0 being lowest and 7 highest priority."""


class InterfaceEntry(BaseModel):
    id: str
    """Unique identifier for the network interface."""
    name: str
    """Name of the network interface."""
    fake: bool
    """Whether this is a fake/simulated interface for testing purposes."""
    type: str
    """Type of interface (PHYSICAL, BRIDGE, LINK_AGGREGATION, VLAN, etc.)."""
    state: InterfaceEntryState
    """Current runtime state information for the interface."""
    aliases: list[InterfaceEntryAlias]
    """List of IP address aliases configured on the interface."""
    ipv4_dhcp: bool
    """Whether IPv4 DHCP is enabled for automatic IP address assignment."""
    ipv6_auto: bool
    """Whether IPv6 autoconfiguration is enabled."""
    description: str
    """Human-readable description of the interface."""
    mtu: int | None
    """Maximum transmission unit size for the interface."""
    vlan_parent_interface: str | None = NotRequired
    """Parent interface for VLAN configuration."""
    vlan_tag: int | None = NotRequired
    """VLAN tag number for VLAN interfaces."""
    vlan_pcp: int | None = NotRequired
    """Priority Code Point for VLAN traffic prioritization."""
    lag_protocol: str = NotRequired
    """Link aggregation protocol (LACP, FAILOVER, LOADBALANCE, etc.)."""
    lag_ports: list[str] = []
    """List of interface names that are members of this link aggregation group."""
    bridge_members: list[str] = []  # FIXME: Please document fields for HA Hardware
    """List of interface names that are members of this bridge."""
    enable_learning: bool = NotRequired
    """Whether MAC address learning is enabled for bridge interfaces."""

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
    """Types of interfaces to exclude from the result."""
    include: list[str] = []
    """Specific interfaces to include even if they would normally be excluded."""


class InterfaceCommitOptions(BaseModel):
    rollback: bool = True
    """Roll back changes in case they fail to apply."""
    checkin_timeout: int = 60
    """Number of seconds to wait for the checkin call to acknowledge the interface changes happened as planned from \
    the user. If checkin does not happen within this period of time, the changes will get reverted."""


class InterfaceCreateFailoverAlias(BaseModel):
    type: Literal["INET", "INET6"] = "INET"
    """The type of IP address (INET for IPv4, INET6 for IPv6)."""
    address: IPvAnyAddress
    """The IP address for the failover alias."""


class InterfaceCreateAlias(InterfaceCreateFailoverAlias):
    netmask: int
    """The network mask in CIDR notation."""


class InterfaceCreate(BaseModel):
    name: str = NotRequired
    """Generate a name if not provided based on `type`, e.g. "br0", "bond1", "vlan0"."""
    description: str = ""
    """Human-readable description of the interface."""
    type: Literal["BRIDGE", "LINK_AGGREGATION", "VLAN"]
    """Type of interface to create."""
    ipv4_dhcp: bool = False
    """Enable IPv4 DHCP for automatic IP address assignment."""
    ipv6_auto: bool = False
    """Enable IPv6 autoconfiguration."""
    aliases: UniqueList[InterfaceCreateAlias] = []
    """List of IP address aliases to configure on the interface."""
    failover_critical: bool = False
    """Whether this interface is critical for failover functionality. Critical interfaces are monitored for \
    failover events and can trigger failover when they fail."""
    failover_group: int | None = NotRequired
    """Failover group identifier for clustering. Interfaces in the same group fail over together during \
    failover events."""
    failover_vhid: Annotated[int, Field(ge=1, le=255)] | None = NotRequired
    """Virtual Host ID for VRRP failover configuration. Must be unique within the VRRP group and match \
    between failover nodes."""
    failover_aliases: list[InterfaceCreateFailoverAlias] = []
    """List of IP aliases for failover configuration. These IPs are assigned to the interface during normal \
    operation and migrate during failover."""
    failover_virtual_aliases: list[InterfaceCreateFailoverAlias] = []
    """List of virtual IP aliases for failover configuration. These are shared IPs that float between nodes \
    during failover events."""
    bridge_members: list = []
    """List of interfaces to add as members of this bridge."""
    enable_learning: bool = True
    """Enable MAC address learning for bridge interfaces. When enabled, the bridge learns MAC addresses \
    from incoming frames and builds a forwarding table to optimize traffic flow."""
    stp: bool = True
    """Enable Spanning Tree Protocol for bridge interfaces. STP prevents network loops by blocking redundant \
    paths and enables automatic failover when the primary path fails."""
    lag_protocol: Literal["LACP", "FAILOVER", "LOADBALANCE", "ROUNDROBIN", "NONE"] = NotRequired
    """Link aggregation protocol to use for bonding interfaces. LACP uses 802.3ad dynamic negotiation, \
    FAILOVER provides active-backup, LOADBALANCE and ROUNDROBIN distribute traffic across links."""
    xmit_hash_policy: Literal["LAYER2", "LAYER2+3", "LAYER3+4", None] = None
    """Transmit hash policy for load balancing in link aggregation. LAYER2 uses MAC addresses, LAYER2+3 adds IP \
    addresses, and LAYER3+4 includes TCP/UDP ports for distribution."""
    lacpdu_rate: Literal["SLOW", "FAST", None] = None
    """LACP data unit transmission rate. SLOW sends LACPDUs every 30 seconds, FAST sends every 1 second for \
    quicker link failure detection."""
    lag_ports: list[str] = []
    """List of interface names to include in the link aggregation group."""
    vlan_parent_interface: str = NotRequired
    """Parent interface for VLAN configuration."""
    vlan_tag: int = Field(ge=1, le=4094, default=NotRequired)
    """VLAN tag number (1-4094)."""
    vlan_pcp: Annotated[int, Field(ge=0, le=7)] | None = NotRequired
    """Priority Code Point for VLAN traffic prioritization (0-7). Values 0-7 map to different QoS priority levels, \
    with 0 being lowest and 7 highest priority."""
    mtu: Annotated[int, Field(ge=68, le=9216)] | None = None
    """Maximum transmission unit size for the interface (68-9216 bytes)."""


class InterfaceIPInUseOptions(BaseModel):
    ipv4: bool = True
    """Include IPv4 addresses in the results."""
    ipv6: bool = True
    """Include IPv6 addresses in the results."""
    ipv6_link_local: bool = False
    """Include IPv6 link-local addresses in the results."""
    loopback: bool = False
    """Return loopback interface addresses."""
    any: bool = False
    """Return wildcard addresses (0.0.0.0 and ::)."""
    static: bool = False
    """Only return configured static IPs."""
    interfaces: list[NonEmptyString] = Field(default_factory=list)
    """Only return IPs from specified interfaces. If empty, returns IPs from all interfaces."""


class InterfaceIPInUseItem(BaseModel):
    type: str
    """The type of IP address (INET for IPv4, INET6 for IPv6)."""
    address: IPvAnyAddress
    """The IP address that is in use."""
    netmask: int
    """The network mask in CIDR notation."""
    broadcast: str = NotRequired
    """The broadcast address for IPv4 networks."""


class InterfaceServicesRestartedOnSyncItem(BaseModel):
    type: str
    """The type of service restart event."""
    service: str
    """The name of the service that was restarted."""
    ips: list[str]
    """List of IP addresses associated with the service restart."""


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
    """No return value for successful cancel rollback operation."""


class InterfaceCheckinArgs(BaseModel):
    pass


class InterfaceCheckinResult(BaseModel):
    result: None
    """No return value for successful checkin operation."""


class InterfaceCheckinWaitingArgs(BaseModel):
    pass


class InterfaceCheckinWaitingResult(BaseModel):
    result: int | None
    """Number of seconds left to wait or `null` if not waiting."""


class InterfaceChoicesArgs(BaseModel):
    options: InterfaceChoicesOptions = Field(default_factory=InterfaceChoicesOptions)
    """Options for filtering interface choices."""


class InterfaceChoicesResult(BaseModel):
    result: dict[str, str]
    """Names and descriptions of available network interfaces."""


class InterfaceCommitArgs(BaseModel):
    options: InterfaceCommitOptions = Field(default_factory=InterfaceCommitOptions)
    """Options for committing interface changes."""


class InterfaceCommitResult(BaseModel):
    result: None
    """No return value for successful commit operation."""


class InterfaceCreateArgs(BaseModel):
    data: InterfaceCreate
    """Configuration data for the new interface."""


class InterfaceCreateResult(BaseModel):
    result: InterfaceEntry
    """The created interface configuration."""


class InterfaceDefaultRouteWillBeRemovedArgs(BaseModel):
    pass


class InterfaceDefaultRouteWillBeRemovedResult(BaseModel):
    result: bool
    """Whether the default route will be removed by the pending changes."""


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
    """Whether there are pending interface changes that need to be committed."""


class InterfaceIpInUseArgs(BaseModel):
    options: InterfaceIPInUseOptions = Field(default_factory=InterfaceIPInUseOptions)
    """Options for filtering IP addresses in use."""


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
    """Send LACPDUs every 30 seconds for standard link monitoring."""
    FAST: Literal["FAST"]
    """Send LACPDUs every 1 second for rapid link failure detection."""


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
    """No return value for successful rollback operation."""


class InterfaceSaveDefaultRouteArgs(BaseModel):
    gateway: IPv4Address
    """IPv4 address of the default gateway to save."""


class InterfaceSaveDefaultRouteResult(BaseModel):
    result: None
    """No return value for successful save default route operation."""


class InterfaceServicesRestartedOnSyncArgs(BaseModel):
    pass


class InterfaceServicesRestartedOnSyncResult(BaseModel):
    result: list[InterfaceServicesRestartedOnSyncItem]
    """List of services that were restarted during interface synchronization."""


class InterfaceUpdateArgs(BaseModel):
    id: str
    """ID of the interface to update."""
    data: InterfaceUpdate
    """Updated interface configuration data."""


class InterfaceUpdateResult(BaseModel):
    result: InterfaceEntry
    """The updated interface configuration."""


class InterfaceVlanParentInterfaceChoicesArgs(BaseModel):
    pass


class InterfaceVlanParentInterfaceChoicesResult(BaseModel):
    result: dict[str, str]
    """Names and descriptions of available interfaces for `vlan_parent_interface` attribute."""


class InterfaceWebsocketInterfaceArgs(BaseModel):
    pass


class InterfaceWebsocketInterfaceResult(BaseModel):
    result: InterfaceEntry | None
    """The interface used for the current websocket connection or `null` if not available."""


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
    """Use MAC addresses for traffic distribution across bond members."""
    LAYER2_3: Literal["LAYER2+3"] = Field(alias="LAYER2+3")
    """Use MAC and IP addresses for traffic distribution across bond members."""
    LAYER3_4: Literal["LAYER3+4"] = Field(alias="LAYER3+4")
    """Use MAC, IP, and TCP/UDP port information for traffic distribution across bond members."""
