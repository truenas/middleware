from pyroute2 import NDB

from .address import AddressMixin
from .bridge import BridgeMixin
from .bits import InterfaceFlags, InterfaceV6Flags
from .lagg import LaggMixin
from .utils import bitmask_to_set, INTERNAL_INTERFACES
from .vlan import VlanMixin
from .vrrp import VrrpMixin
from .ethernet_settings import EthernetHardwareSettings

__all__ = ["Interface", "CLONED_PREFIXES"]

# Keep this as an immutable type since this
# is used all over the place, and we don't want
# the contents to change
CLONED_PREFIXES = ("br", "vlan", "bond")


class Interface(AddressMixin, BridgeMixin, LaggMixin, VlanMixin, VrrpMixin):
    def __init__(self, dev):
        self.name = dev.get_attr('IFLA_IFNAME')
        self._mtu = dev.get_attr('IFLA_MTU') or 0
        self._flags = dev['flags'] or 0
        self._nd6_flags = dev.get_attr('IFLA_AF_SPEC').get_attr('AF_INET6').get_attr('IFLA_INET6_FLAGS') or 0
        self._link_state = f'LINK_STATE_{dev.get_attr("IFLA_OPERSTATE")}'
        self._link_address = dev.get_attr('IFLA_ADDRESS')
        self._permanent_link_address = dev.get_attr('IFLA_PERM_ADDRESS')
        self._cloned = any((
            (self.name.startswith(CLONED_PREFIXES)),
            (self.name.startswith(INTERNAL_INTERFACES))
        ))
        self._rxq = dev.get_attr('IFLA_NUM_RX_QUEUES') or 1
        self._txq = dev.get_attr('IFLA_NUM_TX_QUEUES') or 1
        self._bus = dev.get_attr('IFLA_PARENT_DEV_BUS_NAME')

    def _read(self, name, type_=str):
        return self._sysfs_read(f"/sys/class/net/{self.name}/{name}", type_)

    def _sysfs_read(self, path, type_=str):
        with open(path, "r") as f:
            value = f.read().strip()

        return type_(value)

    @property
    def bus(self):
        return self._bus

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
        return self._mtu

    @mtu.setter
    def mtu(self, value):
        with NDB(log='off') as ndb:
            with ndb.interfaces[self.orig_name] as dev:
                dev['mtu'] = value

        # NDB() synchronizes state but the instantiation
        # of this class won't reflect the changed MTU
        # unless a new instance is created. This is a
        # cheap way of updating the "state".
        self._mtu = value

    @property
    def cloned(self):
        return self._cloned

    @property
    def flags(self):
        return bitmask_to_set(self._flags, InterfaceFlags)

    @property
    def nd6_flags(self):
        return bitmask_to_set(self._nd6_flags, InterfaceV6Flags)

    @property
    def link_state(self):
        return self._link_state

    @property
    def link_address(self):
        return self._link_address

    @property
    def permanent_link_address(self):
        return self._permanent_link_address

    @property
    def rx_queues(self):
        return self._rxq

    @property
    def tx_queues(self):
        return self._txq

    def asdict(self, address_stats=False, vrrp_config=None):
        state = {
            'name': self.name,
            'orig_name': self.orig_name,
            'description': self.description,
            'mtu': self.mtu,
            'cloned': self.cloned,
            'flags': [i.name for i in self.flags],
            'nd6_flags': [i.name for i in self.nd6_flags],
            'capabilities': [],
            'link_state': self.link_state,
            'media_type': '',
            'media_subtype': '',
            'active_media_type': '',
            'active_media_subtype': '',
            'supported_media': [],
            'media_options': None,
            'link_address': self.link_address or '',
            'permanent_link_address': self.permanent_link_address,
            'hardware_link_address': self.permanent_link_address or self.link_address or '',
            'aliases': [i.asdict(stats=address_stats) for i in self.addresses],
            'vrrp_config': vrrp_config,
            'rx_queues': self.rx_queues,
            'tx_queues': self.tx_queues,
        }

        if False:
            # WARNING: this leaks memory because of our horrific design
            # with all these nested subclasses and mixins. There are no
            # consumers of this so disable it for now. This will be
            # fixed properly in later release. This is least intrusive
            # at time of writing.
            with EthernetHardwareSettings(self.name) as dev:
                state.update({
                    'capabilities': dev.enabled_capabilities,
                    'supported_media': dev.supported_media,
                    'media_type': dev.media_type,
                    'media_subtype': dev.media_subtype,
                    'active_media_type': dev.active_media_type,
                    'active_media_subtype': dev.active_media_subtype,
                })

        if self.name.startswith('bond'):
            state.update({
                'protocol': self.protocol.name if self.protocol is not None else self.protocol,
                'ports': [{'name': p, 'flags': [x.name for x in f]} for p, f in self.ports],
                'xmit_hash_policy': self.xmit_hash_policy,
                'lacpdu_rate': self.lacpdu_rate,
            })

        if self.name.startswith('vlan'):
            state.update({
                'parent': self.parent,
                'tag': self.tag,
                'pcp': self.pcp,
            })

        return state

    def up(self):
        with NDB(log='off') as ndb:
            with ndb.interfaces[self.name] as dev:
                # this context manager waits until the interface
                # is up and "ready" before exiting
                dev['state'] = 'up'

    def down(self):
        with NDB(log='off') as ndb:
            with ndb.interfaces[self.name] as dev:
                dev['state'] = 'down'
