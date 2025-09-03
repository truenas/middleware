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
    def miimon(self):
        try:
            return int(self._sysfs_read(self.get_options_path("miimon")).strip())
        except FileNotFoundError:
            return None

    @miimon.setter
    def miimon(self, value):
        run(["ip", "link", "set", self.name, "type", "bond", "miimon", str(value)])

    @property
    def ports(self):
        ports = []
        for port in self._sysfs_read(f"/sys/devices/virtual/net/{self.name}/bonding/slaves").split():
            ports.append((port, set()))
        return ports

    def get_options_path(self, value):
        return str(pathlib.Path(f"/sys/class/net/{self.name}/bonding/").joinpath(value))

    def add_port(self, member_port):
        self.add_ports([member_port])

    def add_ports(self, member_ports):
        with NDB(log='off') as ndb:
            for member in member_ports:
                try:
                    with ndb.interfaces[member] as mp:
                        if mp['state'] == 'up':
                            # caller of this method will up() the interfaces after
                            # the parent bond interface has been fully configured
                            mp['state'] = 'down'
                except KeyError:
                    # interface was added to bond but maybe it no longer exists,
                    # for example, after a reboot
                    logger.warning('Failed adding %r to %r. Interface not found', member, self.name)
                    continue
                else:
                    with ndb.interfaces[self.name] as bond:
                        try:
                            bond.add_port(member)
                        except Exception:
                            logger.warning('Failed adding %r to %r', member, self.name, exc_inf=True)

    def delete_port(self, member_port):
        return self.delete_ports([member_port])

    def delete_ports(self, member_ports):
        with NDB(log='off') as ndb:
            for to_delete in member_ports:
                if not ndb.interfaces.get(to_delete):
                    logger.warning('Failed removing %r from %r. Interface not found', to_delete, self.name)
                else:
                    try:
                        with ndb.interfaces[self.name] as bond:
                            bond.del_port(to_delete)
                    except Exception:
                        logger.warning('Failed removing %r from %r.', to_delete, self.name, exc_info=True)
                        continue
