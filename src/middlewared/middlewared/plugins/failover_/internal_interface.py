import glob

from middlewared.plugins.interface.netif import netif
from middlewared.service import Service


ZSERIES_PCI_ID = 'PCI_ID=8086:10D3'
ZSERIES_PCI_SUBSYS_ID = 'PCI_SUBSYS_ID=8086:A01F'
INTERFACE_GLOB = '/sys/class/net/*/device/uevent'


class InternalInterfaceService(Service):

    class Config:
        private = True
        namespace = 'failover.internal_interface'

    def detect(self):

        hardware = self.middleware.call_sync(
            'failover.hardware'
        )

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

        # Detect X-series and M-series heartbeat interface
        # TODO: Fix this
        if hardware in ('PUMA', 'ECHOWARP'):
            pass

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

        try:
            iface = netif.get_interface(iface)
        except KeyError:
            self.logger.error(f'Internal interface:"{iface}" not found.')
            return

        configured = False
        for address in iface.addresses:
            if address.af != netif.AddressFamily.INET:
                continue

            # Internal interface is already configured
            if str(address.address) == internal_ip:
                configured = True

        if not configured:
            iface.add_address(self.middleware.call_sync('interface.alias_to_addr', {
                'address': internal_ip,
                'netmask': '24',
            }))

        # testing shows that the z-series interface is not brought up automatically
        # so we need to up the interface after we apply the IP address
        iface.up()
