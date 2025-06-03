import os.path
import re
import subprocess
from functools import cache
from pathlib import Path

from middlewared.api import api_method
from middlewared.api.current import FCCapableArgs, FCCapableResult
from middlewared.service import Service, filterable_api_method
from middlewared.service_exception import CallError
from middlewared.utils import filter_list
from .utils import dmi_pci_slot_info

FIBRE_CHANNEL_SEARCH_STRING = 'Fibre Channel'
QLA2XXX_KERNEL_MODULE = 'qla2xxx_scst'
FIBRE_CHANNEL_VENDOR = 'QLogic'
FC_HOST_PAT = re.compile('/sys/devices/(.*)/(?P<host>host.*)/fc_host/(?P=host)')


class FCService(Service):

    class Config:
        private = True
        role_prefix = 'SHARING_ISCSI_TARGET'

    @api_method(
        FCCapableArgs,
        FCCapableResult,
        roles=['SHARING_ISCSI_TARGET_READ']
    )
    async def capable(self):
        """
        Returns True if the system is licensed for FIBRECHANNEL and contains
        one or more Fibre Channel cards.  False otherwise.
        """
        if await self.middleware.call('system.is_enterprise'):
            if await self.middleware.call('system.feature_enabled', 'FIBRECHANNEL'):
                if await self.middleware.call('fc.hba_present'):
                    return True
        return False

    @cache
    def hba_present(self):
        """
        Return True if a Qlogic Fibre Channel card is present.  False otherwise.
        """
        lspci_cmd = ['lspci']
        ret = subprocess.run(lspci_cmd, capture_output=True)
        if ret.returncode:
            error = ret.stderr.decode() if ret.stderr else ret.stdout.decode()
            if not error:
                error = 'No error message reported'
            self.logger.debug('Failed to execute command: lspci with error: %r', error)
            raise CallError(f'Failed to determine serial number/product: {error}')
        for line in ret.stdout.decode().split('\n'):
            if FIBRE_CHANNEL_SEARCH_STRING not in line:
                continue
            if FIBRE_CHANNEL_VENDOR not in line:
                continue
            # We matched!
            return True
        return False

    @filterable_api_method(private=True)
    def fc_hosts(self, filters, options):
        result = []
        if self.middleware.call_sync('fc.capable'):
            self.__load_kernel_module()
            slots = self.middleware.call_sync('fc.slot_info')
            with os.scandir('/sys/class/fc_host') as scan:
                for i in filter(lambda x: x.is_symlink() and x.name.startswith('host'), scan):
                    # Ensure realpath looks something like
                    # '/sys/devices/pci0000:b2/0000:b2:00.0/0000:b3:00.0/host14/fc_host/host14'
                    if srp := FC_HOST_PAT.search(os.path.realpath(i.path)):
                        addr = srp[1]
                        path = Path(i.path)
                        # node_name and port_name must be transported as string to avoid JSON breakage
                        entry = {
                            'name': i.name,
                            'path': i.path,
                            'node_name': (path / 'node_name').read_text().strip(),
                            'port_name': (path / 'port_name').read_text().strip(),
                            'port_type': (path / 'port_type').read_text().strip(),
                            'port_state': (path / 'port_state').read_text().strip(),
                            'model': (path / 'symbolic_name').read_text().strip().split()[0],
                            'speed': (path / 'speed').read_text().strip(),
                            'addr': addr,
                        }
                        # If nothing is connected then port_type and speed can be "Unknown"

                        # Some attributes are only present for real hardware ports
                        for fname in ['max_npiv_vports', 'npiv_vports_inuse']:
                            try:
                                entry[fname] = int((path / fname).read_text().strip())
                            except FileNotFoundError:
                                entry[fname] = None
                        entry['physical'] = entry['max_npiv_vports'] is not None

                        # Get slot information from DMI (dmidecode)
                        # First pull out the piece of PCI address that is also included
                        # in dmidecode output.
                        laddr = addr.split('/')[-1]
                        if laddr in slots:
                            _, function = laddr.rsplit('.', 1)
                            entry['slot'] = f'{slots[laddr]} / PCI Function {function}'
                        else:
                            # The DMI information typically includes function 0
                            # We'll want to also match the slot if we're a different
                            # function.
                            if '.' in laddr:
                                laddr, function = laddr.rsplit('.', 1)
                                zeroaddr = f'{laddr}.0'
                                if zeroaddr in slots:
                                    entry['slot'] = f'{slots[zeroaddr]} / PCI Function {function}'
                        result.append(entry)
        return filter_list(result, filters, options)

    async def fc_host_nport_wwpn_choices(self):
        """
        Return a list of physical N_Port WWPNs on this node.
        """
        # Use more manual cache, so that we can pop it during CI
        try:
            return await self.middleware.call('cache.get', 'fc.fc_host_nport_wwpn_choices')
        except KeyError:
            pass

        result = []
        for fc in (await self.middleware.call('fc.fc_hosts', [["physical", "=", True]])):
            port_name = fc['port_name']
            # Replace the leading '0x' with 'naa.'
            wwpn = f'naa.{port_name[2:]}'
            result.append(wwpn)

        await self.middleware.call('cache.put', 'fc.fc_host_nport_wwpn_choices', result)
        return result

    def __load_kernel_module(self):
        if not os.path.isdir(f'/sys/module/{QLA2XXX_KERNEL_MODULE}'):
            self.logger.info('Loading kernel module %r', QLA2XXX_KERNEL_MODULE)
            try:
                subprocess.run(["modprobe", QLA2XXX_KERNEL_MODULE])
            except subprocess.CalledProcessError as e:
                self.logger.error('Failed to load kernel module. Error %r', e)

    async def load_kernel_module(self):
        """
        Load the Fibre Channel HBA kernel module.
        """
        if await self.middleware.call('fc.capable'):
            await self.middleware.run_in_thread(self.__load_kernel_module)

    @cache
    def slot_info(self):
        """
        Cached wrapper around dmi_pci_slot_info
        """
        return dmi_pci_slot_info()
