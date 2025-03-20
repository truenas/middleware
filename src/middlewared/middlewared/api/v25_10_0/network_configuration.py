from typing import Literal

from pydantic import Field

from middlewared.api.base import BaseModel, ForUpdateMetaclass, Excluded, excluded_field, NotRequired
from middlewared.api.base.types.network import IPvAnyAddress, Hostname, Domain, NameserverAddress


__all__ = [
    "NetworkConfigurationEntry", "NetWorkConfigurationUpdateArgs", "NetworkConfigurationUpdateResult",
    "NetworkConfigurationActivityChoicesArgs", "NetworkConfigurationActivityChoicesResult",
]


class ServiceAnnouncement(BaseModel):
    netbios: bool = NotRequired
    """Enable the NetBIOS name server (NBNS) which starts concurrently with the SMB service. SMB clients will only
    perform NBNS lookups if SMB1 is enabled. NBNS may be required for legacy SMB clients."""
    mdns: bool = NotRequired
    """Enable multicast DNS service announcements for enabled services."""
    wsd: bool = NotRequired
    """Enable Web Service Discovery support."""


class NetworkConfigurationActivity(BaseModel):
    type: Literal["ALLOW", "DENY"]
    activities: list[str] = []


class NetWorkConfigurationState(BaseModel):
    ipv4gateway: IPvAnyAddress
    ipv6gateway: IPvAnyAddress
    nameservers: list[NameserverAddress] = Field(max_length=3)
    hosts: list[str]


class NetworkConfigurationEntry(BaseModel):
    id: int
    hostname: Hostname
    domain: Domain
    ipv4gateway: IPvAnyAddress
    """Used instead of the default gateway provided by DHCP."""
    ipv6gateway: IPvAnyAddress
    nameservers: list[NameserverAddress] = Field(max_length=3)
    """Primary, secondary, and tertiary DNS servers."""
    httpproxy: str
    """Must be provided if a proxy is to be used for network operations."""
    hosts: list[str]
    domains: list[str] = Field(max_length=5)
    service_announcement: ServiceAnnouncement
    """Determines the broadcast protocols that will be used to advertise the server."""
    activity: NetworkConfigurationActivity
    hostname_local: Hostname
    hostname_b: Hostname | None = NotRequired
    hostname_virtual: Hostname | None = NotRequired
    state: NetWorkConfigurationState


class NetWorkConfigurationUpdate(NetworkConfigurationEntry, metaclass=ForUpdateMetaclass):
    id: Excluded = excluded_field()
    hostname_local: Excluded = excluded_field()
    state: Excluded = excluded_field()


class NetworkConfigurationActivityChoicesArgs(BaseModel):
    pass


class NetworkConfigurationActivityChoicesResult(BaseModel):
    result: list[list[str]]


class NetWorkConfigurationUpdateArgs(BaseModel):
    data: NetWorkConfigurationUpdate


class NetworkConfigurationUpdateResult(BaseModel):
    result: NetworkConfigurationEntry
