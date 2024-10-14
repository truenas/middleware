from _pytest.mark import KeywordMatcher
from libvirt import Callable
from middlewared.api.base import BaseModel
from middlewared.service_exception import CallError, ValidationErrors
from middlewared.schema import Error
from typing import Literal, TypeAlias, Optional
from ipaddress import ip_network, ip_interface, ip_address, IPv4Network, IPv4Interface, IPv4Address, IPv6Network, IPv6Interface, IPv6Address

__all__ = ["IPAddr"]

ExcludedAddrTypes: TypeAlias = Literal[
    'MULTICAST',
    'PRIVATE',
    'GLOBAL',
    'UNSPECIFIED',
    'RESERVED',
    'LOOPBACK',
    'LINK_LOCAL'
]

class IPAddr(BaseModel):
    cidr: bool = False
    network: bool = False
    network_strict: bool = False
    address_types: list[ExcludedAddrTypes] = []
    v4: bool = True
    v6: bool = True
    factory: Optional[Callable] = None

    def __init__(self, *args, **kwargs):
        super().__init__()
        if self.v4 and self.v6:
            if self.network:
                self.factory = ip_network
            elif self.cidr:
                self.factory = ip_interface
            else:
                self.factory = ip_address
        elif self.v4:
            if self.network:
                    self.factory = IPv4Network
            elif self.cidr:
                self.factory = IPv4Interface
            else:
                self.factory = IPv4Address
        elif self.v6:
            if self.network:
                self.factory = IPv6Network
            elif self.cidr:
                self.factory = IPv6Interface
            else:
                self.factory = IPv6Address
        else:
            raise ValueError('Either IPv4 or IPv6 should be allowed')

    def __check_permitted_addr_types(self, value):
        if not self.address_types:
            return

        to_check = self.factory(value)

        if isinstance(to_check, (IPv4Interface, IPv6Interface)):
            to_check = to_check.ip

        for addr_type in self.address_types:
            if addr_type not in self.excluded_addr_types:
                raise CallError(
                    f'INTERNAL ERROR: {addr_type} not in supported types. '
                    'This indicates a programming error in API endpoint.'
                )

            if to_check.__getattribute__(f'is_{addr_type.lower()}'):
                raise ValueError(
                    f'{str(to_check)}: {addr_type.lower()} addresses are not permitted.'
                )

    def clean(self, value):
        value = super().clean(value)

        if value:
            try:
                if self.network:
                    value = str(self.factory(value, strict=self.network_strict))
                else:
                    if self.cidr and '/' not in value:
                        raise ValueError(
                            'Specified address should be in CIDR notation, e.g. 192.168.0.2/24'
                        )

                    zone_index = None
                    if self.allow_zone_index and '%' in value:
                        value, zone_index = value.rsplit('%', 1)

                    addr = self.factory(value)

                    if zone_index is not None and not isinstance(addr, IPv6Address):
                        raise ValueError('Zone index is allowed only for IPv6 addresses')

                    value = str(addr)
                    if zone_index is not None:
                        value += f'%{zone_index}'

                self.__check_permitted_addr_types(value)

            except ValueError as e:
                raise Error(self.name, str(e))

        return value

    def validate(self, value):
        if value is None:
            return value

        verrors = ValidationErrors()

        try:
            self.clean(value)
        except (Error, ValueError) as e:
            verrors.add(self.name, str(e))

        verrors.check()

        return super().validate(value)
