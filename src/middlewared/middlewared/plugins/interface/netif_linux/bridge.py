# -*- coding=utf-8 -*-
import json
import logging

import middlewared.plugins.interface.netif_linux.interface as interface

from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["create_bridge", "BridgeMixin"]


def create_bridge(name):
    cmd = [
        "ip", "link", "add", name, "type", "bridge",
        "stp_state", "1"  # enable stp by default 1 == on 0 == off
    ]
    run(cmd)
    interface.Interface(name).up()


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
