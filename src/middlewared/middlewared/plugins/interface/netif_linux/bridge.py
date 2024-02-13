import json
import logging
from pyroute2 import NDB

from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["create_bridge", "BridgeMixin"]


def create_bridge(name):
    with NDB(log="off") as ndb:
        ndb.interfaces.create(ifname=name, kind="bridge").set("state", "up").commit()


class BridgeMixin:
    def add_member(self, name):
        run(["ip", "link", "set", name, "master", self.name])

    def set_learning(self, name, enable):
        run(["bridge", "link", "set", "dev", name, "learning", "on" if enable else "off"])

    def delete_member(self, name):
        run(["ip", "link", "set", name, "nomaster"])

    @property
    def members(self):
        return [
            link["ifname"]
            for link in json.loads(run(["bridge", "-json", "link"]).stdout)
            if link.get("master") == self.name
        ]

    @property
    def stp(self):
        with NDB(log="off") as ndb:
            with ndb.interfaces[self.name] as br:
                return bool(br['br_stp_state'])

    def toggle_stp(self, name, value):
        # 0 is off > 0 is on
        with NDB(log="off") as ndb:
            with ndb.interfaces[name] as br:
                br['br_stp_state'] = value
