from pydantic import model_validator
from middlewared.api.base import BaseModel
from typing import Callable
from ipaddress import ip_network, ip_interface, ip_address, IPv4Network, IPv4Interface, IPv4Address, IPv6Network, IPv6Interface, IPv6Address
from middlewared.service_exception import CallError

excluded_address_types = [
    'MULTICAST',
    'PRIVATE',
    'GLOBAL',
    'UNSPECIFIED',
    'RESERVED',
    'LOOPBACK',
    'LINK_LOCAL'
]

def set_factory(ipaddr: 'IPAddr'):
    if ipaddr.v4 and ipaddr.v6:
        if ipaddr.network:
            ipaddr.factory = ip_network
        elif ipaddr.cidr:
            ipaddr.factory = ip_interface
        else:
            ipaddr.factory = ip_address
    elif ipaddr.v4:
        if ipaddr.network:
            ipaddr.factory = IPv4Network
        elif ipaddr.cidr:
            ipaddr.factory = IPv4Interface
        else:
            ipaddr.factory = IPv4Address
    elif ipaddr.v6:
        if ipaddr.network:
            ipaddr.factory = IPv6Network
        elif ipaddr.cidr:
            ipaddr.factory = IPv6Interface
        else:
            ipaddr.factory = IPv6Address
    else:
        raise ValueError('Either IPv4 or IPv6 should be allowed')

def check_permitted_addr_types(ipaddr: 'IPAddr', value):
    if not ipaddr.address_types:
        return

    to_check = ipaddr.factory(value)

    if isinstance(to_check, (IPv4Interface, IPv6Interface)):
        to_check = to_check.ip

    for addr_type in ipaddr.address_types:
        if addr_type not in excluded_address_types:
            raise CallError(
                f'INTERNAL ERROR: {addr_type} not in supported types. '
                'This indicates a programming error in API endpoint.'
            )

        if to_check.__getattribute__(f'is_{addr_type.lower()}'):
            raise ValueError(
                f'{str(to_check)}: {addr_type.lower()} addresses are not permitted.'
            )

def validate_address(ipaddr: 'IPAddr'):
    value = ipaddr.address
    try:
        if ipaddr.network:
            value = str(ipaddr.factory(value, strict=ipaddr.network_strict))
        else:
            if ipaddr.cidr and '/' not in value:
                raise ValueError(
                    'Specified address should be in CIDR notation, e.g. 192.168.0.2/24'
                )
            zone_index = None
            if ipaddr.allow_zone_index and '%' in value:
                value, zone_index = value.rsplit('%', 1)

            addr = ipaddr.factory(value)

            if zone_index is not None and not isinstance(addr, IPv6Address):
                raise ValueError('Zone index is allowed only for IPv6 addresses')

            value = str(addr)
            if zone_index is not None:
                value += f'%{zone_index}'

        check_permitted_addr_types(ipaddr, value)

    except ValueError as e:
        raise ValueError(ipaddr.address, str(e))

    ipaddr.address = value

class IPAddr(BaseModel):
    address: str
    cidr: bool = False
    network: bool = False
    network_strict: bool = False
    address_types: list[str] = []
    v4: bool = True
    v6: bool = True
    allow_zone_index: bool = False
    factory: Callable | None = None

    @model_validator(mode='after')
    def validate_arguments(self):
        set_factory(self)
        validate_address(self)
        return self

class IPAddrResult(BaseModel):
    result: IPAddr
