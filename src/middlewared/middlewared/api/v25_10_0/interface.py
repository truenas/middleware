from typing import Annotated, Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, IPv4Address, UniqueList, IPvAnyAddress, Excluded, excluded_field, ForUpdateMetaclass,
    single_argument_args, single_argument_result, NotRequired, NonEmptyString,
)


__all__ = [
    "InterfaceEntry", "InterfaceBridgeMembersChoicesArgs", "InterfaceBridgeMembersChoicesResult",
    "InterfaceCancelRollbackArgs", "InterfaceCancelRollbackResult", "InterfaceCheckinArgs", "InterfaceCheckinResult",
    "InterfaceCheckinWaitingArgs", "InterfaceCheckinWaitingResult", "InterfaceChoicesArgs", "InterfaceChoicesResult",
    "InterfaceCommitArgs", "InterfaceCommitResult", "InterfaceCreateArgs", "InterfaceCreateResult",
    "InterfaceNetworkConfigToBeRemovedArgs", "InterfaceNetworkConfigToBeRemovedResult", "InterfaceDeleteArgs",
    "InterfaceDeleteResult", "InterfaceHasPendingChangesArgs", "InterfaceHasPendingChangesResult",
    "InterfaceIpInUseArgs", "InterfaceIpInUseResult", "InterfaceLacpduRateChoicesArgs",
    "InterfaceLacpduRateChoicesResult", "InterfaceLagPortsChoicesArgs", "InterfaceLagPortsChoicesResult",
    "InterfaceRollbackArgs", "InterfaceRollbackResult", "InterfaceSaveNetworkConfigArgs",
    "InterfaceSaveNetworkConfigResult", "InterfaceServicesRestartedOnSyncArgs",
    "InterfaceServicesRestartedOnSyncResult", "InterfaceUpdateArgs", "InterfaceUpdateResult",
    "InterfaceVlanParentInterfaceChoicesArgs", "InterfaceVlanParentInterfaceChoicesResult",
    "InterfaceWebsocketInterfaceArgs", "InterfaceWebsocketInterfaceResult", "InterfaceWebsocketLocalIpArgs",
    "InterfaceWebsocketLocalIpResult", "InterfaceXmitHashPolicyChoicesArgs", "InterfaceXmitHashPolicyChoicesResult",
]


class InterfaceEntryAlias(BaseModel):
    type: str = Field(description="The type of IP address (INET for IPv4, INET6 for IPv6).")
    address: str = Field(description="The IP address value.")
    netmask: str | int = Field(
        description="The network mask for the IP address, either as a string or CIDR notation integer.",
    )


class InterfaceEntryStateAlias(InterfaceEntryAlias):
    netmask: str | int = NotRequired
    broadcast: str = Field(default=NotRequired, description="Broadcast address for the network interface.")


class InterfaceEntryStatePort(BaseModel):
    name: str = Field(description="The name of the port interface.")
    flags: list[str] = Field(description="List of flags associated with the port.")


class InterfaceEntryState(BaseModel):
    name: str = Field(description="Current name of the network interface.")
    orig_name: str = Field(description="Original name of the network interface before any renaming.")
    description: str = Field(description="Human-readable description of the network interface.")
    mtu: int = Field(description="Maximum transmission unit size for the interface.")
    cloned: bool = Field(description="Whether the interface is a cloned/virtual interface.")
    flags: list[str] = Field(
        description=(
            "List of interface flags indicating various states and capabilities. Common flags include UP, DOWN, "
            "RUNNING, MULTICAST, BROADCAST, LOOPBACK, and POINTOPOINT."
        ),
    )
    nd6_flags: list = Field(
        description=(
            "IPv6 neighbor discovery flags. These control IPv6 autoconfiguration behavior and include flags like "
            "AUTO_LINKLOCAL, ACCEPT_RTADV, and PERFORMNUD."
        ),
    )
    capabilities: list = Field(
        description=(
            "List of hardware capabilities supported by the interface. Common capabilities include VLAN_MTU, JUMBO_MTU,"
            " VLAN_HWTAGGING, VLAN_HWCSUM, and TSO4."
        ),
    )
    link_state: str = Field(description="Current link state of the interface (up, down, etc.).")
    media_type: str = Field(
        description="Type of media/connection for the interface. Examples include Ethernet, 802.11, or loopback.",
    )
    media_subtype: str = Field(
        description=(
            "Subtype of media/connection for the interface. Examples include 1000baseT, 100baseTX, or autoselect."
        ),
    )
    active_media_type: str = Field(
        description="Currently active media type. This may differ from configured media_type during autonegotiation.",
    )
    active_media_subtype: str = Field(
        description="Currently active media subtype. This reflects the actual negotiated connection speed and type.",
    )
    supported_media: list = Field(
        description=(
            "List of supported media types for the interface. Contains media descriptors like '1000baseT <full-duplex>'"
            " or 'autoselect'."
        ),
    )
    media_options: list | None = Field(
        description=(
            "Available media options for the interface. Options may include 'full-duplex', 'half-duplex', "
            "'flowcontrol', or 'rxpause'."
        ),
    )
    link_address: str = Field(description="MAC address of the interface.")
    permanent_link_address: str | None = Field(
        description="Permanent MAC address of the interface if different from current.",
    )
    hardware_link_address: str = Field(description="Hardware MAC address of the interface.")
    rx_queues: int = Field(default=NotRequired, description="Number of receive queues configured for the interface.")
    tx_queues: int = Field(default=NotRequired, description="Number of transmit queues configured for the interface.")
    aliases: list[InterfaceEntryStateAlias] = Field(
        description="List of IP address aliases configured on the interface.",
    )
    vrrp_config: list | None = Field(
        default=[],
        description="VRRP (Virtual Router Redundancy Protocol) configuration for the interface.",
    )
    # lagg section
    protocol: str | None = Field(
        default=NotRequired,
        description="Link aggregation protocol used (LACP, FAILOVER, etc.).",
    )
    ports: list[InterfaceEntryStatePort] = Field(
        default=[],
        description="List of ports that are members of this link aggregation group.",
    )
    xmit_hash_policy: str | None = Field(
        default=None,
        description=(
            "Transmit hash policy for load balancing in link aggregation. LAYER2 uses MAC addresses, LAYER2+3 adds IP "
            "addresses, and LAYER3+4 includes TCP/UDP ports for distribution."
        ),
    )
    lacpdu_rate: str | None = Field(
        default=None,
        description=(
            "LACP data unit transmission rate. SLOW sends LACPDUs every 30 seconds, FAST sends every 1 second for "
            "quicker link failure detection."
        ),
    )
    # vlan section
    parent: str | None = Field(default=NotRequired, description="Parent interface for VLAN configuration.")
    tag: int | None = Field(default=NotRequired, description="VLAN tag number.")
    pcp: int | None = Field(
        default=NotRequired,
        description=(
            "Priority Code Point for VLAN traffic prioritization. Values 0-7 map to different QoS priority levels, with"
            " 0 being lowest and 7 highest priority."
        ),
    )


class InterfaceEntry(BaseModel):
    id: str = Field(description="Unique identifier for the network interface.")
    name: str = Field(description="Name of the network interface.")
    fake: bool = Field(description="Whether this is a fake/simulated interface for testing purposes.")
    type: str = Field(description="Type of interface (PHYSICAL, BRIDGE, LINK_AGGREGATION, VLAN, etc.).")
    state: InterfaceEntryState = Field(description="Current runtime state information for the interface.")
    aliases: list[InterfaceEntryAlias] = Field(description="List of IP address aliases configured on the interface.")
    ipv4_dhcp: bool = Field(description="Whether IPv4 DHCP is enabled for automatic IP address assignment.")
    ipv6_auto: bool = Field(description="Whether IPv6 autoconfiguration is enabled.")
    description: str = Field(description="Human-readable description of the interface.")
    mtu: int | None = Field(description="Maximum transmission unit size for the interface.")
    vlan_parent_interface: str | None = Field(
        default=NotRequired,
        description="Parent interface for VLAN configuration.",
    )
    vlan_tag: int | None = Field(default=NotRequired, description="VLAN tag number for VLAN interfaces.")
    vlan_pcp: int | None = Field(
        default=NotRequired,
        description="Priority Code Point for VLAN traffic prioritization.",
    )
    lag_protocol: str = Field(
        default=NotRequired,
        description="Link aggregation protocol (LACP, FAILOVER, LOADBALANCE, etc.).",
    )
    lag_ports: list[str] = Field(
        default=[],
        description="List of interface names that are members of this link aggregation group.",
    )
    bridge_members: list[str] = Field(
        default=[],
        description="List of interface names that are members of this bridge.",
    )  # FIXME: Please document fields for HA Hardware
    enable_learning: bool = Field(
        default=NotRequired,
        description="Whether MAC address learning is enabled for bridge interfaces.",
    )

    class Config:
        extra = "allow"


class InterfaceChoicesOptions(BaseModel):
    bridge_members: bool = Field(default=False, description="Include BRIDGE members.")
    lag_ports: bool = Field(default=False, description="Include LINK_AGGREGATION ports.")
    vlan_parent: bool = Field(default=True, description="Include VLAN parent interface.")
    exclude: list = Field(
        default=["epair", "tap", "vnet"],
        description="Prefixes of interfaces to exclude from the result.",
    )
    exclude_types: list[Literal["BRIDGE", "LINK_AGGREGATION", "PHYSICAL", "UNKNOWN", "VLAN"]] = Field(
        default=[],
        description="Types of interfaces to exclude from the result.",
    )
    include: list[str] = Field(
        default=[],
        description="Specific interfaces to include even if they would normally be excluded.",
    )


class InterfaceCommitOptions(BaseModel):
    rollback: bool = Field(default=True, description="Roll back changes in case they fail to apply.")
    checkin_timeout: int = Field(
        default=60,
        description=(
            "Number of seconds to wait for the checkin call to acknowledge the interface changes happened as planned "
            "from the user. If checkin does not happen within this period of time, the changes will get reverted."
        ),
    )


class InterfaceCreateFailoverAlias(BaseModel):
    type: Literal["INET", "INET6"] = Field(
        default="INET",
        description="The type of IP address (INET for IPv4, INET6 for IPv6).",
    )
    address: IPvAnyAddress = Field(description="The IP address for the failover alias.")


class InterfaceCreateAlias(InterfaceCreateFailoverAlias):
    netmask: int = Field(description="The network mask in CIDR notation.")


class InterfaceCreate(BaseModel):
    name: str = Field(
        default=NotRequired,
        description="Generate a name if not provided based on `type`, e.g. \"br0\", \"bond1\", \"vlan0\".",
    )
    description: str = Field(default="", description="Human-readable description of the interface.")
    type: Literal["BRIDGE", "LINK_AGGREGATION", "VLAN"] = Field(description="Type of interface to create.")
    ipv4_dhcp: bool = Field(default=False, description="Enable IPv4 DHCP for automatic IP address assignment.")
    ipv6_auto: bool = Field(default=False, description="Enable IPv6 autoconfiguration.")
    aliases: UniqueList[InterfaceCreateAlias] = Field(
        default=[],
        description="List of IP address aliases to configure on the interface.",
    )
    failover_critical: bool = Field(
        default=False,
        description=(
            "Whether this interface is critical for failover functionality. Critical interfaces are monitored for "
            "failover events and can trigger failover when they fail."
        ),
    )
    failover_group: int | None = Field(
        default=NotRequired,
        description=(
            "Failover group identifier for clustering. Interfaces in the same group fail over together during failover "
            "events."
        ),
    )
    failover_vhid: Annotated[int, Field(ge=1, le=255)] | None = Field(
        default=NotRequired,
        description=(
            "Virtual Host ID for VRRP failover configuration. Must be unique within the VRRP group and match between "
            "failover nodes."
        ),
    )
    failover_aliases: list[InterfaceCreateFailoverAlias] = Field(
        default=[],
        description=(
            "List of IP aliases for failover configuration. These IPs are assigned to the interface during normal "
            "operation and migrate during failover."
        ),
    )
    failover_virtual_aliases: list[InterfaceCreateFailoverAlias] = Field(
        default=[],
        description=(
            "List of virtual IP aliases for failover configuration. These are shared IPs that float between nodes "
            "during failover events."
        ),
    )
    bridge_members: list = Field(default=[], description="List of interfaces to add as members of this bridge.")
    enable_learning: bool = Field(
        default=True,
        description=(
            "Enable MAC address learning for bridge interfaces. When enabled, the bridge learns MAC addresses from "
            "incoming frames and builds a forwarding table to optimize traffic flow."
        ),
    )
    stp: bool = Field(
        default=True,
        description=(
            "Enable Spanning Tree Protocol for bridge interfaces. STP prevents network loops by blocking redundant "
            "paths and enables automatic failover when the primary path fails."
        ),
    )
    lag_protocol: Literal["LACP", "FAILOVER", "LOADBALANCE", "ROUNDROBIN", "NONE"] = Field(
        default=NotRequired,
        description=(
            "Link aggregation protocol to use for bonding interfaces. LACP uses 802.3ad dynamic negotiation, FAILOVER "
            "provides active-backup, LOADBALANCE and ROUNDROBIN distribute traffic across links."
        ),
    )
    xmit_hash_policy: Literal["LAYER2", "LAYER2+3", "LAYER3+4", None] = Field(
        default=None,
        description=(
            "Transmit hash policy for load balancing in link aggregation. LAYER2 uses MAC addresses, LAYER2+3 adds IP "
            "addresses, and LAYER3+4 includes TCP/UDP ports for distribution."
        ),
    )
    lacpdu_rate: Literal["SLOW", "FAST", None] = Field(
        default=None,
        description=(
            "LACP data unit transmission rate. SLOW sends LACPDUs every 30 seconds, FAST sends every 1 second for "
            "quicker link failure detection."
        ),
    )
    lag_ports: list[str] = Field(
        default=[],
        description="List of interface names to include in the link aggregation group.",
    )
    vlan_parent_interface: str = Field(default=NotRequired, description="Parent interface for VLAN configuration.")
    vlan_tag: int = Field(ge=1, le=4094, default=NotRequired, description="VLAN tag number (1-4094).")
    vlan_pcp: Annotated[int, Field(ge=0, le=7)] | None = Field(
        default=NotRequired,
        description=(
            "Priority Code Point for VLAN traffic prioritization (0-7). Values 0-7 map to different QoS priority "
            "levels, with 0 being lowest and 7 highest priority."
        ),
    )
    mtu: Annotated[int, Field(ge=68, le=9216)] | None = Field(
        default=None,
        description="Maximum transmission unit size for the interface (68-9216 bytes).",
    )


class InterfaceIPInUseOptions(BaseModel):
    ipv4: bool = Field(default=True, description="Include IPv4 addresses in the results.")
    ipv6: bool = Field(default=True, description="Include IPv6 addresses in the results.")
    ipv6_link_local: bool = Field(default=False, description="Include IPv6 link-local addresses in the results.")
    loopback: bool = Field(default=False, description="Return loopback interface addresses.")
    any: bool = Field(default=False, description="Return wildcard addresses (0.0.0.0 and ::).")
    static: bool = Field(default=False, description="Only return configured static IPs.")
    interfaces: list[NonEmptyString] = Field(
        default_factory=list,
        description="Only return IPs from specified interfaces. If empty, returns IPs from all interfaces.",
    )


class InterfaceIPInUseItem(BaseModel):
    type: str = Field(description="The type of IP address (INET for IPv4, INET6 for IPv6).")
    address: IPvAnyAddress = Field(description="The IP address that is in use.")
    netmask: int = Field(description="The network mask in CIDR notation.")
    broadcast: str = Field(default=NotRequired, description="The broadcast address for IPv4 networks.")


class InterfaceServicesRestartedOnSyncItem(BaseModel):
    type: str = Field(description="The type of service restart event.")
    service: str = Field(description="The name of the service that was restarted.")
    ips: list[str] = Field(description="List of IP addresses associated with the service restart.")


class InterfaceUpdate(InterfaceCreate, metaclass=ForUpdateMetaclass):
    type: Excluded = excluded_field()


# -------------------   Args and Results   ------------------- #


class InterfaceBridgeMembersChoicesArgs(BaseModel):
    id: str | None = Field(
        default=None,
        description="Name of existing bridge interface whose member interfaces should be included in the result.",
    )


class InterfaceBridgeMembersChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="IDs of available interfaces that can be added to a bridge interface.")


class InterfaceCancelRollbackArgs(BaseModel):
    pass


class InterfaceCancelRollbackResult(BaseModel):
    result: None = Field(description="No return value for successful cancel rollback operation.")


class InterfaceCheckinArgs(BaseModel):
    pass


class InterfaceCheckinResult(BaseModel):
    result: None = Field(description="No return value for successful checkin operation.")


class InterfaceCheckinWaitingArgs(BaseModel):
    pass


class InterfaceCheckinWaitingResult(BaseModel):
    result: int | None = Field(description="Number of seconds left to wait or `null` if not waiting.")


class InterfaceChoicesArgs(BaseModel):
    options: InterfaceChoicesOptions = Field(
        default_factory=InterfaceChoicesOptions,
        description="Options for filtering interface choices.",
    )


class InterfaceChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="Names and descriptions of available network interfaces.")


class InterfaceCommitArgs(BaseModel):
    options: InterfaceCommitOptions = Field(
        default_factory=InterfaceCommitOptions,
        description="Options for committing interface changes.",
    )


class InterfaceCommitResult(BaseModel):
    result: None = Field(description="No return value for successful commit operation.")


class InterfaceCreateArgs(BaseModel):
    data: InterfaceCreate = Field(description="Configuration data for the new interface.")


class InterfaceCreateResult(BaseModel):
    result: InterfaceEntry = Field(description="The created interface configuration.")


class InterfaceNetworkConfigToBeRemovedArgs(BaseModel):
    pass


class InterfaceNetworkConfigToBeRemovedResult(BaseModel):
    result: list[Literal["ipv4gateway", "nameserver1", "nameserver2", "nameserver3"]] = Field(
        description=(
            "The network configuration fields that will be wiped on the next `interface.checkin` call. The current "
            "values of these fields can be retrieved by calling `network.configuration.config`."
        ),
    )


class InterfaceDeleteArgs(BaseModel):
    id: str = Field(description="ID of the interface to delete.")


class InterfaceDeleteResult(BaseModel):
    result: str = Field(description="ID of the interface that was deleted.")


class InterfaceHasPendingChangesArgs(BaseModel):
    pass


class InterfaceHasPendingChangesResult(BaseModel):
    result: bool = Field(description="Whether there are pending interface changes that need to be committed.")


class InterfaceIpInUseArgs(BaseModel):
    options: InterfaceIPInUseOptions = Field(
        default_factory=InterfaceIPInUseOptions,
        description="Options for filtering IP addresses in use.",
    )


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
    SLOW: Literal["SLOW"] = Field(description="Send LACPDUs every 30 seconds for standard link monitoring.")
    FAST: Literal["FAST"] = Field(description="Send LACPDUs every 1 second for rapid link failure detection.")


class InterfaceLagPortsChoicesArgs(BaseModel):
    id: str | None = Field(
        default=None,
        description="Name of existing bond interface whose member interfaces should be included in the result.",
    )


class InterfaceLagPortsChoicesResult(BaseModel):
    result: dict[str, str] = Field(description="IDs of available interfaces that can be added to a bond interface.")


class InterfaceRollbackArgs(BaseModel):
    pass


class InterfaceRollbackResult(BaseModel):
    result: None = Field(description="No return value for successful rollback operation.")


@single_argument_args("config")
class InterfaceSaveNetworkConfigArgs(BaseModel):
    ipv4gateway: IPv4Address = Field(description="IPv4 address of the default gateway to save.")
    nameserver1: IPvAnyAddress = Field(default=NotRequired, description="Primary DNS server.")
    nameserver2: IPvAnyAddress = Field(default=NotRequired, description="Secondary DNS server.")
    nameserver3: IPvAnyAddress = Field(default=NotRequired, description="Tertiary DNS server.")


class InterfaceSaveNetworkConfigResult(BaseModel):
    result: None = Field(description="No return value for successful save default route operation.")


class InterfaceServicesRestartedOnSyncArgs(BaseModel):
    pass


class InterfaceServicesRestartedOnSyncResult(BaseModel):
    result: list[InterfaceServicesRestartedOnSyncItem] = Field(
        description="List of services that were restarted during interface synchronization.",
    )


class InterfaceUpdateArgs(BaseModel):
    id: str = Field(description="ID of the interface to update.")
    data: InterfaceUpdate = Field(description="Updated interface configuration data.")


class InterfaceUpdateResult(BaseModel):
    result: InterfaceEntry = Field(description="The updated interface configuration.")


class InterfaceVlanParentInterfaceChoicesArgs(BaseModel):
    pass


class InterfaceVlanParentInterfaceChoicesResult(BaseModel):
    result: dict[str, str] = Field(
        description="Names and descriptions of available interfaces for `vlan_parent_interface` attribute.",
    )


class InterfaceWebsocketInterfaceArgs(BaseModel):
    pass


class InterfaceWebsocketInterfaceResult(BaseModel):
    result: InterfaceEntry | None = Field(
        description="The interface used for the current websocket connection or `null` if not available.",
    )


class InterfaceWebsocketLocalIpArgs(BaseModel):
    pass


class InterfaceWebsocketLocalIpResult(BaseModel):
    result: IPvAnyAddress | None = Field(
        description="The local IP address for the current websocket session or `null`.",
    )


class InterfaceXmitHashPolicyChoicesArgs(BaseModel):
    pass


@single_argument_result
class InterfaceXmitHashPolicyChoicesResult(BaseModel):
    LAYER2: Literal["LAYER2"] = Field(description="Use MAC addresses for traffic distribution across bond members.")
    LAYER2_3: Literal["LAYER2+3"] = Field(
        alias="LAYER2+3",
        description="Use MAC and IP addresses for traffic distribution across bond members.",
    )
    LAYER3_4: Literal["LAYER3+4"] = Field(
        alias="LAYER3+4",
        description="Use MAC, IP, and TCP/UDP port information for traffic distribution across bond members.",
    )
