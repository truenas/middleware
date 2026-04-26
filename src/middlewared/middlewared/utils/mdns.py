# NOTE: tests are provided in src/middlewared/middlewared/pytest/unit/utils/test_mdns.py
# Any updates to this file should have corresponding updates to tests

import enum

from typing import Any
from .filter_list import filter_list


class DevType(enum.Enum):
    AIRPORT = 'AirPort'
    APPLETV = 'AppleTv1,1'
    MACPRO = 'MacPro'
    MACPRORACK = 'MacPro7,1@ECOLOR=226,226,224'
    RACKMAC = 'RackMac'
    TIMECAPSULE = 'TimeCapsule6,106'
    XSERVE = 'Xserve'

    def __str__(self) -> str:
        return self.value


def ip_addresses_to_interface_names(
    ifaces: list[dict[str, Any]], ip_addresses: list[str],
) -> list[str]:
    """Resolve a list of IP addresses to the interface names they live on.

    `ifaces` - results of interface.query

    `ip_addresses` - list of ip_addresses the service is supposed to be
    bound to.

    truenas-discoveryd's service files and shared [discovery] section take
    interface names (e.g. `eth0`), not kernel interface indexes. Returns
    the set of interface names (`iface['id']`) whose address list matches
    any of `ip_addresses`, in a stable (sorted) order.
    """
    iface_filter: list[list[Any]] = [['OR', [
        ['state.aliases.*.address', 'in', ip_addresses],
        ['state.failover_virtual_aliases.*.address', 'in', ip_addresses],
    ]]]
    return sorted({iface['id'] for iface in filter_list(ifaces, iface_filter)})
