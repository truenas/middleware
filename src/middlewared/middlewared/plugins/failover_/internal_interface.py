import glob

from pyroute2 import NDB

from middlewared.service import Service
from middlewared.utils.functools import cache


ZSERIES_PCI_ID = 'PCI_ID=8086:10D3'
ZSERIES_PCI_SUBSYS_ID = 'PCI_SUBSYS_ID=8086:A01F'
INTERFACE_GLOB = '/sys/class/net/*/device/uevent'


class InternalInterfaceService(Service):

    class Config:
        private = True
        namespace = 'failover.internal_interface'

    @cache
    def detect(self):
        hardware = self.middleware.call_sync('failover.hardware')
        # Return BHYVE heartbeat interface
        if hardware == 'BHYVE':
            return ['enp0s6f1']

        # Detect Z-series heartbeat interface
        if hardware == 'ECHOSTREAM':
            for i in glob.iglob(INTERFACE_GLOB):
                with open(i, 'r') as f:
                    data = f.read()

                    if ZSERIES_PCI_ID and ZSERIES_PCI_SUBSYS_ID in data:
                        return [i.split('/')[4].strip()]

        if hardware in ('PUMA', 'ECHOWARP', 'F1'):
            return ['ntb0']

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
