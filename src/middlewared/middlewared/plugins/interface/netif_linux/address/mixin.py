# -*- coding=utf-8 -*-
import ipaddress
import logging

import netifaces

from middlewared.plugins.interface.netif_linux.utils import run

from .ipv6 import ipv6_netmask_to_prefixlen
from .types import AddressFamily, InterfaceAddress, LinkAddress

logger = logging.getLogger(__name__)

__all__ = ["AddressMixin"]


class AddressMixin:
    def add_address(self, address):
        self._address_op("add", address)

    def flush(self):
        # Remove all configured ip addresses
        run(['ip', 'addr', 'flush', 'dev', self.name, 'scope', 'global'])

    def remove_address(self, address):
        self._address_op("del", address)

    def replace_address(self, address):
        self._address_op("replace", address)

    def _address_op(self, op, address):
        if isinstance(address.address, LinkAddress):
            return

        netmask = str(address.netmask)
        if isinstance(address.address, ipaddress.IPv6Address):
            netmask = ipv6_netmask_to_prefixlen(netmask)

        cmd = ["ip", "addr", op, f"{address.address}/{netmask}"]
        if op == 'add':
            # make sure we tell linux to assign proper broadcast address
            # when adding an IPv4 address to an interface
            # (doesn't apply to IPv6)
            cmd.extend(["brd", "+"]) if ':' not in f'{address.address}' else None
        cmd.extend(["dev", self.name])

        run(cmd)

    @property
    def addresses(self):
        addresses = []

        try:
            iface = netifaces.ifaddresses(self.name)
        except Exception:
            # a ValueError will be raised when this function is given an interface
            # that doesn't exist on the host OS. How might we get to this point for
            # an interface that doesn't exist on the OS you might wonder? PCI passthrough
            # is how. By the time this method is called the NIC existed on the host
            # OS but was gobbled up by the VM which removes it from the host OS entirely.
            return addresses

        for family, family_addresses in iface.items():
            try:
                af = AddressFamily(family)
            except ValueError:
                logger.warning("Unknown address family %r for interface %r", family, self.name)
                continue

            for addr in family_addresses:
                if af is AddressFamily.LINK:
                    address = LinkAddress(self.name, addr["addr"])
                elif af is AddressFamily.INET:
                    address = ipaddress.IPv4Interface(f'{addr["addr"]}/{addr["netmask"]}')
                elif af is AddressFamily.INET6:
                    try:
                        if "/" in addr["netmask"]:
                            prefixlen = int(addr["netmask"].split("/")[1])
                        else:
                            prefixlen = ipv6_netmask_to_prefixlen(addr["netmask"])
                    except ValueError:
                        logger.warning("Invalid IPv6 netmask %r for interface %r", addr["netmask"], self.name)
                        continue

                    address = ipaddress.IPv6Interface(f'{addr["addr"].split("%")[0]}/{prefixlen}')
                else:
                    continue

                addresses.append(InterfaceAddress(af, address))

        return addresses
