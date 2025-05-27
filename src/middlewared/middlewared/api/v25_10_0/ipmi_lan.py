from ipaddress import IPv4Address
from typing import Annotated, Literal

from pydantic import AfterValidator, Field, Secret

from middlewared.api.base import BaseModel, query_result, ForUpdateMetaclass
from middlewared.api.base.validators import passwd_complexity_validator
from .common import QueryFilters, QueryOptions


__all__ = [
    "IPMILanEntry", "IPMILanQueryArgs", "IPMILanQueryResult", "IPMILanChannelsArgs",
    "IPMILanChannelsResult", "IPMILanUpdateArgs", "IPMILanUpdateResult",
]


class IPMILanEntry(BaseModel, metaclass=ForUpdateMetaclass):
    channel: int
    id_: int = Field(alias="id")
    ip_address_source: str
    ip_address: str
    mac_address: str
    subnet_mask: str
    default_gateway_ip_address: str
    default_gateway_mac_address: str
    backup_gateway_ip_address: str
    backup_gateway_mac_address: str
    vlan_id: int | None
    vlan_id_enable: bool
    vlan_priority: int


class IPMILanQueryOptions(BaseModel):
    query_remote: bool = Field(alias='query-remote', default=False)


class IPMILanQuery(BaseModel):
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default_factory=QueryOptions)
    ipmi_options: IPMILanQueryOptions = Field(alias='ipmi-options', default_factory=IPMILanQueryOptions)


class IPMILanUpdateOptionsDHCP(BaseModel):
    dhcp: Literal[True] = True
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
    dhcp: Literal[False] = False
    """Provide a static IP address."""
    ipaddress: IPv4Address
    """The IPv4 address in the form of `192.168.1.150`."""
    netmask: IPv4Address
    """The netmask in the form of `255.255.255.0`."""
    gateway: IPv4Address
    """The gateway in the form of `192.168.1.1`."""


class IPMILanQueryArgs(BaseModel):
    data: IPMILanQuery = Field(default_factory=IPMILanQuery)


IPMILanQueryResult = query_result(IPMILanEntry)


class IPMILanChannelsArgs(BaseModel):
    pass


class IPMILanChannelsResult(BaseModel):
    result: list[int]


class IPMILanUpdateArgs(BaseModel):
    channel: int
    data: IPMILanUpdateOptionsDHCP | IPMILanUpdateOptionsStatic = Field(discriminator="dhcp")


class IPMILanUpdateResult(BaseModel):
    result: int
