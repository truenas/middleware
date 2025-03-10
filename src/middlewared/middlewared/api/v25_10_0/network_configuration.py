from typing import Annotated, Literal

from pydantic import IPvAnyAddress as IPvAnyAddress_, Field, AfterValidator

from middlewared.api.base import BaseModel, ForUpdateMetaclass, Excluded, excluded_field, NotRequired


__all__ = [
    "NetworkConfigurationEntry", "NetWorkConfigurationUpdateArgs", "NetworkConfigurationUpdateResult",
    "NetworkConfigurationActivityChoicesArgs", "NetworkConfigurationActivityChoicesResult",
]


def validate_ipaddr(address: str):
    """Return the original string instead of an ipaddress object."""
    IPvAnyAddress_(address)
    return address


def validate_nameserver(address: str):
    nameserver = IPvAnyAddress_(address)
    error = None

    if nameserver.is_loopback:
        error = 'Loopback is not a valid nameserver'
    elif nameserver.is_unspecified:
        error = 'Unspecified addresses are not valid as nameservers'
    elif nameserver.version == 4:
        if address == '255.255.255.255':
            error = 'This is not a valid nameserver address'
        elif address.startswith('169.254'):
            error = '169.254/16 subnet is not valid for nameserver'

    if error:
        raise ValueError(error)

    return address


Hostname = Annotated[str, Field(pattern=r'^[a-zA-Z\.\-0-9]*[a-zA-Z0-9]$')]
Domain = Annotated[str, Field(pattern=r'^[a-zA-Z\.\-0-9]*$')]
IPvAnyAddress =  Literal[''] | Annotated[str, AfterValidator(validate_ipaddr)]
NameserverAddress = Literal[''] | Annotated[str, AfterValidator(validate_nameserver)]


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
    nameservers: tuple[NameserverAddress, NameserverAddress, NameserverAddress]
    hosts: list[str]


class NetworkConfigurationEntry(BaseModel):
    id: int
    hostname: Hostname
    domain: Domain
    ipv4gateway: IPvAnyAddress
    """Used instead of the default gateway provided by DHCP."""
    ipv6gateway: IPvAnyAddress
    nameservers: tuple[NameserverAddress, NameserverAddress, NameserverAddress]
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
