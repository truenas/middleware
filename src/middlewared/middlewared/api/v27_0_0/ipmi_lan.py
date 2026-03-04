from typing import Annotated, Literal

from pydantic import AfterValidator, Field, Secret

from middlewared.api.base import BaseModel, IPv4Address, query_result, ForUpdateMetaclass, passwd_complexity_validator
from .common import QueryFilters, QueryOptions


__all__ = [
    "IPMILanEntry", "IPMILanQueryArgs", "IPMILanQueryResult", "IPMILanChannelsArgs",
    "IPMILanChannelsResult", "IPMILanUpdateArgs", "IPMILanUpdateResult",
]


class IPMILanEntry(BaseModel, metaclass=ForUpdateMetaclass):
    channel: int
    """IPMI LAN channel number."""
    id_: int = Field(alias="id")
    """Unique identifier for the IPMI LAN configuration."""
    ip_address_source: str
    """Source type for IP address assignment (e.g., "DHCP", "Static")."""
    ip_address: str
    """Current IP address assigned to the IPMI interface."""
    mac_address: str
    """MAC address of the IPMI network interface."""
    subnet_mask: str
    """Subnet mask for the IPMI network interface."""
    default_gateway_ip_address: str
    """IP address of the default gateway."""
    default_gateway_mac_address: str
    """MAC address of the default gateway."""
    backup_gateway_ip_address: str
    """IP address of the backup gateway."""
    backup_gateway_mac_address: str
    """MAC address of the backup gateway."""
    vlan_id: int | None
    """VLAN ID number or `null` if VLAN is not configured."""
    vlan_id_enable: bool
    """Whether VLAN tagging is enabled for this interface."""
    vlan_priority: int
    """VLAN priority level for tagged packets."""


class IPMILanQueryOptions(BaseModel):
    query_remote: bool = Field(alias='query-remote', default=False)
    """Whether to query remote IPMI LAN configuration on HA systems."""


class IPMILanQuery(BaseModel):
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    """Query filters to apply to IPMI LAN configuration results."""
    query_options: QueryOptions = Field(alias='query-options', default_factory=QueryOptions)
    """Query options for sorting and pagination."""
    ipmi_options: IPMILanQueryOptions = Field(alias='ipmi-options', default_factory=IPMILanQueryOptions)
    """IPMI-specific query options."""


class IPMILanUpdateOptionsDHCP(BaseModel):
    dhcp: Literal[True]
    """Turn on DHCP protocol for IP address management."""
    password: Secret[
        Annotated[
            str,
            AfterValidator(passwd_complexity_validator(
                required_types=["ASCII_UPPER", "ASCII_LOWER", "DIGIT", "SPECIAL"],
                required_cnt=3,
                min_length=8,
                max_length=16,
            ))
        ] | None
    ] = None
    """The password to be applied. Must be between 8 and 16 characters long and \
    contain only ascii upper,lower, 0-9, and special characters."""
    vlan: Annotated[int, Field(ge=0, le=4096)] | None = None
    """The vlan tag number. A null value disables tagging."""
    apply_remote: bool = False
    """If on an HA system, and this field is set to True, \
    the settings will be sent to the remote controller."""


class IPMILanUpdateOptionsStatic(IPMILanUpdateOptionsDHCP):
    dhcp: Literal[False]
    """Provide a static IP address."""
    ipaddress: IPv4Address
    """The IPv4 address in the form of `192.168.1.150`."""
    netmask: IPv4Address
    """The netmask in the form of `255.255.255.0`."""
    gateway: IPv4Address
    """The gateway in the form of `192.168.1.1`."""


class IPMILanQueryArgs(BaseModel):
    data: IPMILanQuery = Field(default_factory=IPMILanQuery)
    """Query parameters for IPMI LAN configuration."""


IPMILanQueryResult = query_result(IPMILanEntry)


class IPMILanChannelsArgs(BaseModel):
    pass


class IPMILanChannelsResult(BaseModel):
    result: list[int]
    """Array of available IPMI LAN channel numbers."""


class IPMILanUpdateArgs(BaseModel):
    channel: int
    """IPMI LAN channel number to update."""
    data: IPMILanUpdateOptionsDHCP | IPMILanUpdateOptionsStatic = Field(discriminator="dhcp")
    """IPMI LAN configuration data (DHCP or static IP)."""


class IPMILanUpdateResult(BaseModel):
    result: int
    """Returns the channel number that was updated."""
