from _pytest.mark import KeywordMatcher
from libvirt import Callable
from middlewared.api.base import BaseModel
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

    def fdsfs(self, **kwargs):
        super().__init__(**kwargs)
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
