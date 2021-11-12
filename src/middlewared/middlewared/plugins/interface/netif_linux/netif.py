import logging
from pyroute2 import NDB

from .bridge import create_bridge
from .interface import Interface, CLONED_PREFIXES
from .lagg import AggregationProtocol, create_lagg
from .utils import run
from .vlan import create_vlan

logger = logging.getLogger(__name__)

__all__ = ["AggregationProtocol", "create_vlan", "create_interface", "destroy_interface", "get_interface",
           "list_interfaces", "CLONED_PREFIXES"]


def create_interface(name):
    if name.startswith("br"):
        create_bridge(name)
        return name

    if name.startswith("bond"):
        create_lagg(name)
        return name

    raise ValueError(f"Invalid interface name: {name!r}")


def destroy_interface(name):
    if name.startswith(("bond", "br", "vlan", "kube-bridge")):
        run(["ip", "link", "delete", name])
    else:
        run(["ip", "link", "set", name, "down"])


def get_interface(name):
    return list_interfaces()[name]


def list_interfaces():
    with NDB(log="off") as ndb:
        return {i.ifname: Interface(i.ifname) for i in ndb.interfaces}
