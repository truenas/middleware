from pathlib import Path

from pyroute2 import NDB

from middlewared.service import Service
from middlewared.utils.functools import cache


class InternalInterfaceService(Service):

    class Config:
        private = True
        namespace = 'failover.internal_interface'

    @cache
    def detect(self):
        hardware = self.middleware.call_sync('failover.hardware')
        if hardware == 'BHYVE':
            return ['enp0s6f1']
        elif hardware == 'ECHOSTREAM':
            # z-series
            for i in Path('/sys/class/net/').iterdir():
                try:
                    data = (i / 'device/uevent').read_text()
                    if 'PCI_ID=8086:10D3' in data and 'PCI_SUBSYS_ID=8086:A01F' in data:
                        return [i.name]
                except FileNotFoundError:
                    continue
        elif hardware in ('PUMA', 'ECHOWARP', 'LAJOLLA2'):
            # {x/m/f}-series
            return ['ntb0']
        else:
            return []

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
        with NDB(log='off') as ndb:
            try:
                with ndb.interfaces[iface] as dev:
                    if not any(i.address == internal_ip for i in dev.ipaddr.summary()):
                        dev.add_ip(f'{internal_ip}/24').set(state='up')
            except KeyError:
                return
