import enum
import logging
import pathlib
from pyroute2 import NDB

from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["AggregationProtocol", "create_lagg"]


class AggregationProtocol(enum.Enum):
    LACP = "802.3ad"
    FAILOVER = "active-backup"
    LOADBALANCE = "balance-xor"


def create_lagg(name):
    with NDB(log="off") as ndb:
        ndb.interfaces.create(ifname=name, kind="bond").set("state", "up").commit()


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
    def primary_interface(self):
        if self.protocol == AggregationProtocol.FAILOVER:
            return self._sysfs_read(self.get_options_path("primary")).strip() or None

    @primary_interface.setter
    def primary_interface(self, value):
        run(["ip", "link", "set", self.name, "type", "bond", "primary", value])

    @property
    def ports(self):
        ports = []
        for port in self._sysfs_read(f"/sys/devices/virtual/net/{self.name}/bonding/slaves").split():
            ports.append((port, set()))
        return ports

    def get_options_path(self, value):
        return str(pathlib.Path(f"/sys/class/net/{self.name}/bonding/").joinpath(value))

    def add_port(self, member_port):
        with NDB(log='off') as ndb:
            try:
                with ndb.interfaces[member_port] as mp:
                    if mp['state'] == 'up':
                        # caller of this method will up() the interfaces after
                        # the parent bond interface has been fully configured
                        mp['state'] = 'down'
            except KeyError:
                # interface was added to bond but maybe it no longer exists,
                # for example, after a reboot
                self.logger.warning('Member port %r not found for %r', member_port, self.name)
                return

            with ndb.interfaces[self.name] as bond:
                bond.add_port(member_port)

    def delete_port(self, name):
        run(["ip", "link", "set", name, "nomaster"])
