import asyncio
import os

from middlewared.service import CallError, Service
from middlewared.utils import run
from middlewared.utils.nvmet.spdk import nvmf_ready

from .constants import PORT_ADDR_FAMILY, PORT_TRTYPE

SETUP_SH = '/opt/spdk/scripts/setup.sh'


class NVMetSPDKService(Service):

    class Config:
        private = True
        namespace = 'nvmet.spdk'

    async def _run_setup(self, *args, **kwargs):
        command = [SETUP_SH, *args]
        cp = await run(command, **kwargs)
        if cp.returncode:
            return False
        return True

    async def setup(self):
        """
        Perform necessary setup for SPDK.

        Allocate hugepages and bind PCI devices.
        """
        _slots = await self.slots()
        my_env = os.environ.copy()
        if _slots:
            my_env['PCI_ALLOWED'] = " ".join(_slots)
        else:
            my_env['PCI_ALLOWED'] = "none"
        return await self._run_setup('config', env=my_env)

    async def reset(self):
        """
        Rebind PCI devices back to their original drivers.

        Also cleanup any leftover spdk files/resources.
        Hugepage memory size will remain unchanged.
        """
        return await self._run_setup('reset')

    async def cleanup(self):
        """
        Remove any orphaned files that can be left in the system after SPDK application exit
        """
        return await self._run_setup('cleanup')

    async def slots(self):
        # For the time being we are NOT going to support dedicated NICs that
        # will be devoted to NVMe-oF.  So we will return the empty list.
        return []
        # _nics = await self.nics()
        # return await self.middleware.call('nvmet.spdk.pci_slots', _nics)

    def pci_slots(self, nics):
        pci_slots = []
        for nic in nics:
            with open(f'/sys/class/net/{nic}/device/uevent', 'r') as f:
                for line in f:
                    if line.startswith('PCI_SLOT_NAME='):
                        if slot := line.strip().split('=', 1)[1]:
                            pci_slots.append(slot)
                            break
        if len(nics) != len(pci_slots):
            raise CallError("Could not find PCI slot for every NIC")
        return pci_slots

    async def nics(self):
        """
        Return a list of NIC names corresponding to all configure NVMe-oF ports.
        """
        # Check that kernel nvmet is not enabled
        if (await self.middleware.call('nvmet.global.config'))['kernel']:
            raise CallError("NVMe-oF configured for kernel target")

        # Need to obtain the PCI devices associated with configured ports
        ports = await self.middleware.call('nvmet.port.query')
        if not ports:
            raise CallError("No ports configured for NVMe-oF")

        # For the time being we only support TCP/RDMA with IPv6/IPv6
        if do_failover := await self.middleware.call('failover.licensed'):
            node = await self.middleware.call('failover.node')
            choices = {}
        addresses = set()
        for port in ports:
            if port['addr_trtype'] not in [PORT_TRTYPE.TCP.api, PORT_TRTYPE.RDMA.api]:
                raise CallError(f"Unsupported addr_trtype: {port['addr_trtype']!r}")
            if port['addr_adrfam'] not in [PORT_ADDR_FAMILY.IPV4.api, PORT_ADDR_FAMILY.IPV6.api]:
                raise CallError(f"Unsupported addr_adrfam: {port['addr_adrfam']!r}")
            if do_failover:
                # HA get the non-VIP address (this works on MASTER too)
                trtype = port['addr_trtype']
                if trtype not in choices:
                    choices[trtype] = await self.middleware.call('nvmet.port.transport_address_choices', trtype, True)
                try:
                    pair = choices[trtype][port['addr_traddr']]
                except KeyError:
                    continue
                match node:
                    case 'A':
                        addresses.add(pair.split('/')[0])
                    case 'B':
                        addresses.add(pair.split('/')[1])
            else:
                # Not HA, just use whatever address is in the config
                addresses.add(port['addr_traddr'])

        if not addresses:
            raise CallError("No IP addresses configured for NVMe-oF")

        # Now query the interfaces to discover which ones are being used
        nics = []
        iface_filter = [['OR', [
            ['state.aliases.*.address', 'in', addresses],
            ['state.failover_virtual_aliases.*.address', 'in', addresses]
        ]]]
        interfaces = await self.middleware.call('interface.query', iface_filter)
        for address in addresses:
            name = self._address_to_iface_name(address, interfaces)
            if not name:
                raise CallError(f"Could not find interface for address: {address}")
            nics.append(name)

        return nics

    def _address_to_iface_name(self, address, interfaces):
        for iface in interfaces:
            for alias in iface.get('state', {}).get('aliases', []):
                if alias.get('address') == address:
                    return iface['name']
            for alias in iface.get('state', {}).get('failover_virtual_aliases', []):
                if alias.get('address') == address:
                    return iface['name']

    def nvmf_ready(self, cheap=False):
        return nvmf_ready(cheap)

    async def wait_nvmf_ready(self, retries=10):
        while retries > 0:
            if await self.middleware.call('nvmet.spdk.nvmf_ready'):
                return True
            await asyncio.sleep(1)
            retries -= 1
        return False
