from typing import Literal

from pydantic import Field

from middlewared.api.base import (
    BaseModel, ForUpdateMetaclass, IPvAnyAddress, Hostname, Domain, Excluded, excluded_field, NotRequired,
)


__all__ = [
    "NetworkConfigurationEntry", "NetworkConfigurationUpdateArgs", "NetworkConfigurationUpdateResult",
    "NetworkConfigurationActivityChoicesArgs", "NetworkConfigurationActivityChoicesResult",
]


class ServiceAnnouncement(BaseModel):
    netbios: bool = Field(
        default=NotRequired,
        description=(
            "Enable the NetBIOS name server (NBNS) which starts concurrently with the SMB service. SMB clients will "
            "only perform NBNS lookups if SMB1 is enabled. NBNS may be required for legacy SMB clients."
        ),
    )
    mdns: bool = Field(
        default=NotRequired,
        description="Enable multicast DNS service announcements for enabled services.",
    )
    wsd: bool = Field(default=NotRequired, description="Enable Web Service Discovery support.")


class NetworkConfigurationActivity(BaseModel):
    type: Literal["ALLOW", "DENY"] = Field(description="Whether to allow or deny the specified network activities.")
    activities: list[str] = Field(default=[], description="Array of network activity types to allow or deny.")


class NetWorkConfigurationState(BaseModel):
    ipv4gateway: IPvAnyAddress = Field(description="Current IPv4 default gateway address.")
    ipv6gateway: IPvAnyAddress = Field(description="Current IPv6 default gateway address.")
    nameserver1: IPvAnyAddress = Field(description="Current primary DNS server address.")
    nameserver2: IPvAnyAddress = Field(description="Current secondary DNS server address.")
    nameserver3: IPvAnyAddress = Field(description="Current tertiary DNS server address.")
    hosts: list[str] = Field(description="Current hosts file entries.")


class NetworkConfigurationEntry(BaseModel):
    id: int = Field(description="Unique identifier for the network configuration.")
    hostname: Hostname = Field(description="System hostname.")
    domain: Domain = Field(description="System domain name.")
    ipv4gateway: IPvAnyAddress = Field(description="Used instead of the default gateway provided by DHCP.")
    ipv6gateway: IPvAnyAddress = Field(description="IPv6 default gateway address.")
    nameserver1: IPvAnyAddress = Field(description="Primary DNS server.")
    nameserver2: IPvAnyAddress = Field(description="Secondary DNS server.")
    nameserver3: IPvAnyAddress = Field(description="Tertiary DNS server.")
    httpproxy: str = Field(description="Must be provided if a proxy is to be used for network operations.")
    hosts: list[str] = Field(description="Static host entries to add to the hosts file.")
    domains: list[str] = Field(description="Additional domain names for DNS search.")
    service_announcement: ServiceAnnouncement = Field(
        description="Determines the broadcast protocols that will be used to advertise the server.",
    )
    activity: NetworkConfigurationActivity = Field(description="Network activity filtering configuration.")
    hostname_local: Hostname = Field(description="Local hostname for this system.")
    hostname_b: Hostname | None = Field(
        default=NotRequired,
        description="Hostname for the second controller in HA configurations or `null`.",
    )
    hostname_virtual: Hostname | None = Field(
        default=NotRequired,
        description="Virtual hostname for HA configurations or `null`.",
    )
    state: NetWorkConfigurationState = Field(description="Current network configuration state.")


class NetWorkConfigurationUpdate(NetworkConfigurationEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    hostname_local: Excluded = excluded_field()
    state: Excluded = excluded_field()


class NetworkConfigurationActivityChoicesArgs(BaseModel):
    pass


class NetworkConfigurationActivityChoicesResult(BaseModel):
    result: list[list[str]] = Field(description="Array of available network activity choices for filtering.")


class NetworkConfigurationUpdateArgs(BaseModel):
    data: NetWorkConfigurationUpdate = Field(description="Network configuration data to update.")


class NetworkConfigurationUpdateResult(BaseModel):
    result: NetworkConfigurationEntry = Field(description="The updated network configuration.")
