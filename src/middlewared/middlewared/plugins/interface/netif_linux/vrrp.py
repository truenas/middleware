# -*- coding=utf-8 -*-
import logging

from middlewared.services import Service
from middlewared.plugins.interface.netif import netif

logger = logging.getLogger(__name__)

__all__ = ["VrrpConfig", "VrrpMixin"]


class VrrpConfig():

    def __init__(self, addr=None, state=None):
        self.addr = addr
        self.state = state

    def __getstate__(self):

        return {
            'address': self.addr,
            'state': self.state,
        }


class VrrpMixin(Service):

    @property
    def vrrp_config(self, ifname):

        # query db for configured settings
        info = self.middleware.call_sync(
            'datastore.query',
            'network.interfaces',
            [('int_interface', '=', ifname)],
        )
        configured_vips = [i['int_vip'] for i in info]

        # get current addresses on interface
        iface = netif.get_interface(ifname)
        iface_addrs = [
            str(i.address) for i in iface.addresses if i.af == netif.AddressFamily.INET
        ]

        # check if the configured VIP is on the interface
        for i in configured_vips:
            if i in iface_addrs:
                yield VrrpConfig(addr=i, state='MASTER')

            # VIP is not on the interface which means it's
            # considered in the BACKUP state
            yield VrrpConfig(addr=i, state='BACKUP')

    @vrrp_config.setter
    def vrrp_config(self, addr):

        """
        Not used/needed at the moment since keepalived assigns
        the ip to the interface on service startup depending
        on the election process.
        """
        pass
