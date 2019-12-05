# -*- coding=utf-8 -*-
import glob
import logging
import os
import re
import subprocess

import middlewared.plugins.interface.netif_linux.interface as interface

from .utils import run

logger = logging.getLogger(__name__)

__all__ = ["create_vlan", "VlanMixin"]


def create_vlan(name, parent, tag):
    try:
        run(["ip", "link", "add", "link", parent, "name", name, "type", "vlan", "id", str(tag)])
    except subprocess.CalledProcessError as e:
        if e.stderr.startswith("Cannot find device "):
            raise FileNotFoundError(e.stderr)

        raise

    interface.Interface(name).up()


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
