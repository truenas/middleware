from typing import Literal

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, Excluded, IPvAnyAddress, Hostname, Domain, excluded_field, NotRequired,
)


__all__ = [
    "NetworkConfigurationEntry", "NetworkConfigurationUpdateArgs", "NetworkConfigurationUpdateResult",
    "NetworkConfigurationActivityChoicesArgs", "NetworkConfigurationActivityChoicesResult",
]


class ServiceAnnouncement(BaseModel):
    netbios: bool = NotRequired
    """Enable the NetBIOS name server (NBNS) which starts concurrently with the SMB service. SMB clients will only \
    perform NBNS lookups if SMB1 is enabled. NBNS may be required for legacy SMB clients."""
    mdns: bool = NotRequired
    """Enable multicast DNS service announcements for enabled services."""
    wsd: bool = NotRequired
    """Enable Web Service Discovery support."""


class NetworkConfigurationActivity(BaseModel):
    type: Literal["ALLOW", "DENY"]
    """Whether to allow or deny the specified network activities."""
    activities: list[str] = []
    """Array of network activity types to allow or deny."""


class NetWorkConfigurationState(BaseModel):
    ipv4gateway: IPvAnyAddress
    """Current IPv4 default gateway address."""
    ipv6gateway: IPvAnyAddress
    """Current IPv6 default gateway address."""
    nameserver1: IPvAnyAddress
    """Current primary DNS server address."""
    nameserver2: IPvAnyAddress
    """Current secondary DNS server address."""
    nameserver3: IPvAnyAddress
    """Current tertiary DNS server address."""
    hosts: list[str]
    """Current hosts file entries."""


class NetworkConfigurationEntry(BaseModel):
    id: int
    """Unique identifier for the network configuration."""
    hostname: Hostname
    """System hostname."""
    domain: Domain
    """System domain name."""
    ipv4gateway: IPvAnyAddress
    """Used instead of the default gateway provided by DHCP."""
    ipv6gateway: IPvAnyAddress
    """IPv6 default gateway address."""
    nameserver1: IPvAnyAddress
    """Primary DNS server."""
    nameserver2: IPvAnyAddress
    """Secondary DNS server."""
    nameserver3: IPvAnyAddress
    """Tertiary DNS server."""
    httpproxy: str
    """Must be provided if a proxy is to be used for network operations."""
    hosts: list[str]
    """Static host entries to add to the hosts file."""
    domains: list[str]
    """Additional domain names for DNS search."""
    service_announcement: ServiceAnnouncement
    """Determines the broadcast protocols that will be used to advertise the server."""
    activity: NetworkConfigurationActivity
    """Network activity filtering configuration."""
    hostname_local: Hostname
    """Local hostname for this system."""
    hostname_b: Hostname | None = NotRequired
    """Hostname for the second controller in HA configurations or `null`."""
    hostname_virtual: Hostname | None = NotRequired
    """Virtual hostname for HA configurations or `null`."""
    state: NetWorkConfigurationState
    """Current network configuration state."""


class NetWorkConfigurationUpdate(NetworkConfigurationEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    hostname_local: Excluded = excluded_field()
    state: Excluded = excluded_field()


class NetworkConfigurationActivityChoicesArgs(BaseModel):
    pass


class NetworkConfigurationActivityChoicesResult(BaseModel):
    result: list[list[str]]
    """Array of available network activity choices for filtering."""


class NetworkConfigurationUpdateArgs(BaseModel):
    data: NetWorkConfigurationUpdate
    """Network configuration data to update."""


class NetworkConfigurationUpdateResult(BaseModel):
    result: NetworkConfigurationEntry
    """The updated network configuration."""
