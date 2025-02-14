from ipaddress import IPv4Address
from typing import Annotated

from pydantic import AfterValidator, Field, SecretStr

from middlewared.api.base import BaseModel, ForUpdateMetaclass, NotRequired, query_result
from middlewared.api.base.validators import passwd_complexity_validator
from .common import QueryFilters, QueryOptions


class IPMILanQueryEntry(BaseModel, metaclass=ForUpdateMetaclass):
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


class IPMILanQueryArgs(BaseModel):
    query_filters: QueryFilters = Field(alias='query-filters', default=[])
    query_options: QueryOptions = Field(alias='query-options', default=QueryOptions())
    ipmi_options: IPMILanQueryOptions = Field(alias='ipmi-options', default=IPMILanQueryOptions())


class IPMILanQueryResult(BaseModel):
    result: query_result(IPMILanQueryEntry)


class IPMILanChannelsArgs(BaseModel):
    pass


class IPMILanChannelsResult(BaseModel):
    result: list[int]


class IPMILanUpdateOptions(BaseModel):
    dhcp: bool = NotRequired
    """Turn on DHCP protocol for ip address management"""
    ipddress: IPv4Address = NotRequired
    """The IPv4 address in the form of `192.168.1.150`"""
    netmask: IPv4Address = NotRequired
    """The netmask in the form of `255.255.255.0`"""
    gateway: IPv4Address = NotRequired
    """The gateway in the form of `192.168.1.1`"""
    password: Annotated[
        SecretStr,
        AfterValidator(
            passwd_complexity_validator(
                required_types=["ASCII_UPPER", "ASCII_LOWER", "DIGIT", "SPECIAL"],
                required_cnt=3,
                min_length=8,
                max_length=16,
            )
        )
    ] | None = None
    """The password to be applied. Must be between 8 and 16 characters long and
    contain only ascii upper,lower, 0-9, and special characters."""
    vlan_id: int = Field(ge=0, le=4096, default=NotRequired)
    """The vlan tag number"""
    apply_remote: bool = Field(default=False)
    """If on an HA system, and this field is set to True,
    the settings will be sent to the remote controller."""


class IPMILanUpdateArgs(BaseModel):
    channel: int
    data: IPMILanUpdateOptions


class IPMILanUpdateResult(BaseModel):
    result: int
