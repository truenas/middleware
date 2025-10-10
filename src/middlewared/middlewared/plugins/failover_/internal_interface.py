# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import ipaddress
from pathlib import Path

from pyroute2 import NDB

from middlewared.service import Service
from middlewared.utils.functools_ import cache


class InternalInterfaceService(Service):

    http_site = None

    class Config:
        private = True
        namespace = 'failover.internal_interface'

    @cache
    def detect(self):
        found = list()
        hardware = self.middleware.call_sync('failover.hardware')
        if hardware == 'BHYVE':
            found.append('enp0s6f1')
        elif hardware == 'IXKVM':
            found.append('enp1s0')
        elif hardware == 'ECHOSTREAM':
            # z-series
            for i in Path('/sys/class/net/').iterdir():
                try:
                    data = (i / 'device/uevent').read_text()
                    if 'PCI_ID=8086:10D3' in data and 'PCI_SUBSYS_ID=8086:A01F' in data:
                        found.append(i.name)
                        break
                except FileNotFoundError:
                    continue
        elif hardware in ('PUMA', 'ECHOWARP', 'LAJOLLA2', 'SUBLIGHT'):
            # {x/m/f/h}-series
            found.append('ntb0')
        elif hardware in ('LUDICROUS', 'PLAID'):
            # v-series
            found.append('internode0')
        return tuple(found)

    async def pre_sync(self):
        if not await self.middleware.call('system.is_enterprise'):
            return

        node = await self.middleware.call('failover.node')
        if node == 'A':
            internal_ip = '169.254.10.1'
        elif node == 'B':
            internal_ip = '169.254.10.2'
        else:
            self.logger.error('Node position could not be determined.')
            return

        iface = await self.middleware.call('failover.internal_interfaces')
        if not iface:
            self.logger.error('Internal interface not found.')
            return

        iface = iface[0]

        await self.middleware.run_in_thread(self.sync, iface, internal_ip)

    def sync(self, iface, internal_ip):
        default_table, rtn_blackhole = 254, 6
        with NDB(log='off') as ndb:
            try:
                with ndb.interfaces[iface] as dev:
                    dev.add_ip(f'{internal_ip}/24').set(state='up')
            except KeyError:
                # ip address already exists on this interface
                pass

            # add a blackhole route of 169.254.10.0/23 which is 1 bit larger than
            # ip address we put on the internal interface. We do this because the
            # f-series platform uses AMD ntb driver and the behavior for when the
            # B controller is active and the A controller reboots, is that the ntb0
            # interface is removed from the B controller. This means any src/dst
            # traffic on the 169.254.10/24 subnet will be forwarded out of the gateway
            # of last resort (default route). Since this is internal traffic, we
            # obviously don't want to forward this traffic to the default gateway.
            # This just routes the data into oblivion (drops it).
            dst_network = ipaddress.ip_interface(f'{internal_ip}/23').network.exploded
            try:
                ndb.routes.create(dst=dst_network, table=default_table, type=rtn_blackhole).commit()
            except KeyError:
                # blackhole route already exists
                pass

        self.middleware.call_sync('failover.internal_interface.post_sync', internal_ip)

    async def post_sync(self, internal_ip):
        if self.http_site is None:
            self.http_site = await self.middleware.start_tcp_site(internal_ip)


async def __event_system_ready(middleware, event_type, args):
    await middleware.call('failover.internal_interface.pre_sync')


async def setup(middleware):
    # on HA systems, we bind ourselves on 127.0.0.1:6000, however
    # often times developers/CI/CD do `systemctl restart middlewared`
    # which will tear down the local listening socket so we need to
    # be sure and set it up everytime middleware starts. This is a
    # NO-OP otherwise.
    middleware.event_subscribe('system.ready', __event_system_ready)
    if await middleware.call('system.ready'):
        await middleware.call('failover.internal_interface.pre_sync')
