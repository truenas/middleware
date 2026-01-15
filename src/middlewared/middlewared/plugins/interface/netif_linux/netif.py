import logging
from pyroute2 import IPRoute, NetlinkDumpInterrupted

from .address.netlink import get_address_netlink
from .bridge import create_bridge
from .interface import Interface, CLONED_PREFIXES
from .lagg import AggregationProtocol, create_lagg
from .utils import run
from .vlan import create_vlan

logger = logging.getLogger(__name__)

__all__ = ["AggregationProtocol", "create_vlan", "create_interface", "destroy_interface", "get_address_netlink",
           "get_interface", "list_interfaces", "CLONED_PREFIXES"]


def create_interface(name):
    if name.startswith("br"):
        create_bridge(name)
        return name

    if name.startswith("bond"):
        create_lagg(name)
        return name

    raise ValueError(f"Invalid interface name: {name!r}")


def destroy_interface(name):
    if name.startswith(("bond", "br", "vlan")):
        run(["ip", "link", "delete", name])
    else:
        run(["ip", "link", "set", name, "down"])


def get_interface(name, safe_retrieval=False):
    ifaces = list_interfaces()
    return ifaces.get(name) if safe_retrieval else ifaces[name]


def list_interfaces():
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            with IPRoute() as ipr:
                return {dev.get_attr('IFLA_IFNAME'): Interface(dev) for dev in ipr.get_links()}
        except NetlinkDumpInterrupted:
            if attempt < max_retries:
                # When the kernel is producing a dump of a kernel structure
                # over multiple netlink messages, and the structure changes
                # mid-way, NLM_F_DUMP_INTR is added to the header flags.
                # This an indication that the requested dump contains
                # inconsistent data and must be re-requested. See function
                # nl_dump_check_consistent() in include/net/netlink.h. The
                # pyroute2 library raises this specific exception for this
                # scenario so we'll try again (up to a max of 3 times).
                continue
            else:
                raise
