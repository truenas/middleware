import json
import logging
from pyroute2 import NDB

from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["create_bridge", "BridgeMixin"]


def create_bridge(name):
    with NDB(log="off") as ndb:
        ndb.interfaces.create(ifname=name, kind="bridge").set("br_stp_state", 1).set("state", "up").commit()


class BridgeMixin:
    def add_member(self, name):
        run(["ip", "link", "set", name, "master", self.name])

    def delete_member(self, name):
        run(["ip", "link", "set", name, "nomaster"])

    @property
    def members(self):
        return [
            link["ifname"]
            for link in json.loads(run(["bridge", "-json", "link"]).stdout)
            if link.get("master") == self.name
        ]
