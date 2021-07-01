import enum
import logging
import pathlib

import middlewared.plugins.interface.netif_linux.interface as interface
from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["AggregationProtocol", "create_lagg"]


class AggregationProtocol(enum.Enum):
    LACP = "802.3ad"
    FAILOVER = "active-backup"
    LOADBALANCE = "balance-xor"


def create_lagg(name):
    run(["ip", "link", "add", name, "type", "bond"])
    interface.Interface(name).up()


class LaggMixin:

    @property
    def protocol(self):
        value = self._sysfs_read(f"/sys/devices/virtual/net/{self.name}/bonding/mode").split()[0]
        for protocol in AggregationProtocol:
            if protocol.value == value:
                return protocol

    @protocol.setter
    def protocol(self, value):
        for port in self.ports:
            self.delete_port(port[0])
        run(["ip", "link", "set", self.name, "type", "bond", "mode", value.value])

    @property
    def xmit_hash_policy(self):
        if self.protocol in (AggregationProtocol.LACP, AggregationProtocol.LOADBALANCE):
            # this option only applies to 802.3ad and/or balance-xor
            return self._sysfs_read(self.get_options_path("xmit_hash_policy")).split()[0]

    @xmit_hash_policy.setter
    def xmit_hash_policy(self, value):
        run(["ip", "link", "set", self.name, "type", "bond", "xmit_hash_policy", value])

    @property
    def lacpdu_rate(self):
        if self.protocol == AggregationProtocol.LACP:
            # this option only applies to 802.3ad
            return self._sysfs_read(self.get_options_path("lacp_rate")).split()[0]

    @lacpdu_rate.setter
    def lacpdu_rate(self, value):
        run(["ip", "link", "set", self.name, "type", "bond", "lacp_rate", value])

    @property
    def ports(self):
        ports = []
        for port in self._sysfs_read(f"/sys/devices/virtual/net/{self.name}/bonding/slaves").split():
            ports.append((port, set()))
        return ports

    def get_options_path(self, value):
        return str(pathlib.Path(f"/sys/class/net/{self.name}/bonding/").joinpath(value))

    def add_port(self, name):
        interface.Interface(name).down()
        run(["ip", "link", "set", name, "master", self.name])

    def delete_port(self, name):
        run(["ip", "link", "set", name, "nomaster"])
