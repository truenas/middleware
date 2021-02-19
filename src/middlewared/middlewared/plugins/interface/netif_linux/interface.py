# -*- coding=utf-8 -*-
import logging
import subprocess

from .address import AddressFamily, AddressMixin
from .bridge import BridgeMixin
from .bits import InterfaceFlags, InterfaceLinkState
from .lagg import LaggMixin
from .utils import bitmask_to_set, run
from .vlan import VlanMixin
from .vrrp import VrrpMixin

logger = logging.getLogger(__name__)

__all__ = ["Interface"]

CLONED_PREFIXES = [
    'lo', 'tun', 'tap', 'br', 'vlan', 'bond', 'docker', 'veth', 'kube-bridge', 'kube-dummy', 'vnet', 'openvpn',
]


class Interface(AddressMixin, BridgeMixin, LaggMixin, VlanMixin, VrrpMixin):
    def __init__(self, name):
        self.name = name

    def _read(self, name, type=str):
        return self._sysfs_read(f"/sys/class/net/{self.name}/{name}", type)

    def _sysfs_read(self, path, type=str):
        with open(path, "r") as f:
            value = f.read().strip()

        return type(value)

    @property
    def orig_name(self):
        return self.name

    @property
    def description(self):
        return self.name

    @description.setter
    def description(self, value):
        pass

    @property
    def mtu(self):
        return self._read("mtu", int)

    @mtu.setter
    def mtu(self, mtu):
        up = InterfaceFlags.UP in self.flags
        run(["ip", "link", "set", "dev", self.name, "mtu", str(mtu)])
        if up:
            self.down()
            self.up()

    @property
    def cloned(self):
        for i in CLONED_PREFIXES:
            if self.orig_name.startswith(i):
                return True

        return False

    @property
    def flags(self):
        return bitmask_to_set(self._read("flags", lambda s: int(s, base=16)), InterfaceFlags)

    @property
    def nd6_flags(self):
        return set()

    @nd6_flags.setter
    def nd6_flags(self, value):
        pass

    @property
    def capabilities(self):
        return set()

    @property
    def link_state(self):
        operstate = self._read("operstate")

        return {
            "down": InterfaceLinkState.LINK_STATE_DOWN,
            "up": InterfaceLinkState.LINK_STATE_UP,
        }.get(operstate, InterfaceLinkState.LINK_STATE_UNKNOWN)

    @property
    def link_address(self):
        try:
            return list(filter(lambda x: x.af == AddressFamily.LINK, self.addresses)).pop()
        except IndexError:
            return None

    def __getstate__(self, address_stats=False, media=False, vrrp_config=None):
        state = {
            'name': self.name,
            'orig_name': self.orig_name,
            'description': self.description,
            'mtu': self.mtu,
            'cloned': self.cloned,
            'flags': [i.name for i in self.flags],
            'nd6_flags': [i.name for i in self.nd6_flags],
            'capabilities': [i.name for i in self.capabilities],
            'link_state': self.link_state.name,
            'media_type': '',
            'media_subtype': '',
            'active_media_type': '',
            'active_media_subtype': '',
            'supported_media': [],
            'media_options': None,
            'link_address': self.link_address.address.address if self.link_address is not None else '',
            'aliases': [i.__getstate__(stats=address_stats) for i in self.addresses],
            'vrrp_config': vrrp_config,
        }

        if media:
            p = subprocess.run(["ethtool", self.name], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               encoding="utf-8", errors="ignore")
            if p.returncode == 0:
                ethtool = {
                    k.strip(): v.strip()
                    for k, v in map(lambda s: s.split(":", 1), [line for line in p.stdout.splitlines() if ":" in line])
                }
                if "Speed" in ethtool:
                    bits = [ethtool["Speed"]]
                    if "Port" in ethtool:
                        bits.append(ethtool["Port"])
                    media_subtype = " ".join(bits)

                    state.update({
                        "media_type": "Ethernet",
                        "media_subtype": "autoselect" if ethtool.get("Auto-negotiation") == "on" else media_subtype,
                        "active_media_type": "Ethernet",
                        "active_media_subtype": media_subtype,
                    })

        if self.name.startswith('bond'):
            state.update({
                'protocol': self.protocol.name,
                'ports': [{'name': p, 'flags': [x.name for x in f]} for p, f in self.ports]
            })

        if self.name.startswith('vlan'):
            state.update({
                'parent': self.parent,
                'tag': self.tag,
                'pcp': self.pcp,
            })

        return state

    def up(self):
        run(["ip", "link", "set", self.name, "up"])

    def down(self):
        run(["ip", "link", "set", self.name, "down"])
