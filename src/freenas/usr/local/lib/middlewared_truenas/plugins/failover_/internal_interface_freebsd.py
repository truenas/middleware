import subprocess

from middlewared.plugins.interface.netif import netif
from middlewared.service import Service


class InternalInterfaceService(Service):

    class Config:
        private = True
        namespace = 'failover.internal_interface'

    def detect(self):

        hardware = self.middleware.call_sync(
            'failover.hardware'
        )

        if hardware == 'ECHOSTREAM':
            proc = subprocess.check_output(
                '/usr/sbin/pciconf -lv | grep "card=0xa01f8086 chip=0x10d38086"',
                shell=True,
                encoding='utf8',
            )
            if proc:
                return [proc.split('@')[0]]

        if hardware in ('ECHOWARP', 'PUMA'):
            return ['ntb0']

        if hardware == 'BHYVE':
            return ['vtnet1']

        return []

    async def pre_sync(self):

        hardware = await self.middleware.call('failover.hardware')
        if hardware == 'MANUAL':
            self.logger.error('HA hardware detection failed.')
            return

        node = await self.middleware.call('failover.node')
        if node == 'A':
            carp1_skew = 20
            carp2_skew = 80
            internal_ip = '169.254.10.1'
        elif node == 'B':
            carp1_skew = 80
            carp2_skew = 20
            internal_ip = '169.254.10.2'
        else:
            self.logger.error('Node position could not be determined.')
            return

        iface = await self.middleware.call('failover.internal_interfaces')
        if not iface:
            self.logger.error('Internal interface not found.')
            return

        iface = iface[0]

        await self.middleware.run_in_thread(
            self.sync, iface, carp1_skew, carp2_skew, internal_ip
        )

    def sync(self, iface, carp1_skew, carp2_skew, internal_ip):

        try:
            iface = netif.get_interface(iface)
        except KeyError:
            self.logger.error(f'Internal interface:"{iface}" not found.')
            return

        carp1_addr = '169.254.10.20'
        carp2_addr = '169.254.10.80'

        found_i = found_1 = found_2 = False
        for address in iface.addresses:
            if address.af != netif.AddressFamily.INET:
                continue
            if str(address.address) == internal_ip:
                found_i = True
            elif str(address.address) == carp1_addr:
                found_1 = True
            elif str(address.address) == carp2_addr:
                found_2 = True
            else:
                iface.remove_address(address)

        # VHID needs to be configured before aliases
        found = 0
        for carp_config in iface.carp_config:
            if carp_config.vhid == 10 and carp_config.advskew == carp1_skew:
                found += 1
            elif carp_config.vhid == 20 and carp_config.advskew == carp2_skew:
                found += 1
            else:
                found -= 1

        if found != 2:
            iface.carp_config = [
                netif.CarpConfig(10, advskew=carp1_skew),
                netif.CarpConfig(20, advskew=carp2_skew),
            ]

        if not found_i:
            iface.add_address(self.middleware.call_sync('interface.alias_to_addr', {
                'address': internal_ip,
                'netmask': '24',
            }))

        if not found_1:
            iface.add_address(self.middleware.call_sync('interface.alias_to_addr', {
                'address': carp1_addr,
                'netmask': '32',
                'vhid': 10,
            }))

        if not found_2:
            iface.add_address(self.middleware.call_sync('interface.alias_to_addr', {
                'address': carp2_addr,
                'netmask': '32',
                'vhid': 20,
            }))
