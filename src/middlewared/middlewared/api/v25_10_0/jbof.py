import ipaddress
from typing import Literal

from pydantic import Secret, Field, field_validator

from middlewared.api.base import (
    BaseModel, IPvAnyAddress, Excluded, excluded_field, NotRequired, ForUpdateMetaclass, IPv4Address, IPv6Address
)


__all__ = [
    'JBOFEntry', 'JBOFCreateArgs', 'JBOFCreateResult', 'JBOFDeleteArgs', 'JBOFDeleteResult', 'JBOFLicensedArgs',
    'JBOFLicensedResult', 'JBOFReapplyConfigArgs', 'JBOFReapplyConfigResult', 'JBOFSetMgmtIPArgs',
    'JBOFSetMgmtIPResult', 'JBOFUpdateArgs', 'JBOFUpdateResult',
]


class JBOFEntry(BaseModel):
    id: int
    description: str = NotRequired
    """Optional description of the JBOF."""
    mgmt_ip1: IPvAnyAddress
    """IP of first Redfish management interface."""
    mgmt_ip2: IPvAnyAddress = NotRequired
    """Optional IP of second Redfish management interface."""
    mgmt_username: str
    """Redfish administrative username."""
    mgmt_password: Secret[str]
    """Redfish administrative password."""


class JBOFCreate(JBOFEntry):
    id: Excluded = excluded_field()


class StaticIPv4Address(BaseModel):
    address: IPv4Address = NotRequired
    netmask: str = NotRequired
    gateway: IPv4Address = NotRequired

    @field_validator('netmask')
    @classmethod
    def validate_netmask(cls, value: str) -> str:
        if value.isdigit():
            raise ValueError('Please specify expanded netmask, e.g. 255.255.255.128')

        try:
            ipaddress.ip_network(f'1.1.1.1/{value}', strict=False)
        except ValueError:
            raise ValueError('Not a valid netmask')


class StaticIPv6Address(BaseModel):
    address: IPv6Address = NotRequired
    prefixlen: int = Field(ge=1, le=64, default=NotRequired)


class JBOFSetMgmtIPIOMNetwork(BaseModel):
    dhcp: bool = NotRequired
    fqdn: str = NotRequired
    hostname: str = NotRequired
    ipv4_static_addresses: list[StaticIPv4Address] | None = None
    ipv6_static_addresses: list[StaticIPv6Address] | None = None
    nameservers: list[IPvAnyAddress] | None = None


class JBOFUpdate(JBOFCreate, metaclass=ForUpdateMetaclass):
    pass


class JBOFCreateArgs(BaseModel):
    data: JBOFCreate


class JBOFCreateResult(BaseModel):
    result: JBOFEntry


class JBOFDeleteArgs(BaseModel):
    id: int
    force: bool = False


class JBOFDeleteResult(BaseModel):
    result: Literal[True]


class JBOFLicensedArgs(BaseModel):
    pass


class JBOFLicensedResult(BaseModel):
    result: int
    """Number of JBOF units licensed."""


class JBOFReapplyConfigArgs(BaseModel):
    pass


class JBOFReapplyConfigResult(BaseModel):
    result: None


class JBOFSetMgmtIPArgs(BaseModel):
    id: int
    iom: Literal['IOM1', 'IOM2']
    iom_network: JBOFSetMgmtIPIOMNetwork = Field(default_factory=JBOFSetMgmtIPIOMNetwork)
    ethindex: int = 1
    force: bool = False
    check: bool = True


class JBOFSetMgmtIPResult(BaseModel):
    result: None


class JBOFUpdateArgs(BaseModel):
    id: int
    data: JBOFUpdate


class JBOFUpdateResult(BaseModel):
    result: JBOFEntry
