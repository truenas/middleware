import glob
import logging
import os
import re
from pyroute2 import NDB

from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["create_vlan", "VlanMixin"]


def create_vlan(name, parent, tag):
    with NDB(log="off") as ndb:
        ndb.interfaces[parent].set("state", "up").commit()  # make sure parent is up
        ndb.interfaces.create(ifname=name, link=parent, vlan_id=tag, kind="vlan").set("state", "up").commit()


class VlanMixin:
    @property
    def parent(self):
        return os.path.basename(os.readlink(glob.glob(f"/sys/devices/virtual/net/{self.name}/lower_*")[0]))

    @property
    def tag(self):
        with open(f"/proc/net/vlan/{self.name}") as f:
            return int(re.search(r"VID: ([0-9]+)", f.read()).group(1))

    @property
    def pcp(self):
        return None

    def configure(self, parent, tag, pcp):
        create_vlan(self.name, parent, tag)

    def unconfigure(self):
        run(["ip", "link", "delete", self.name])
