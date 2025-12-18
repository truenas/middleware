import json
import subprocess
from pathlib import Path

from middlewared.api import api_method
from middlewared.api.base import BaseModel
from middlewared.api.current import (RDMACapableProtocolsArgs, RDMACapableProtocolsResult, RDMAGetCardChoicesArgs,
                                     RDMAGetCardChoicesResult, RdmaLinkConfig)
from middlewared.plugins.rdma.interface import RDMAInterfaceService  # noqa (just import to start the service)
from middlewared.service import Service, private
from middlewared.service_exception import CallError
from middlewared.utils.functools_ import cache
from .constants import RDMAprotocols

PRODUCT_NAME_PREFIX = 'Product Name: '
SERIAL_NUMBER_PREFIX = '[SN] Serial number: '
PART_NUMBER_PREFIX = '[PN] Part number: '


class RdmaLinkConfigArgs(BaseModel):
    all: bool = False


class RdmaLinkConfigResult(BaseModel):
    result: list[RdmaLinkConfig]


class RDMAService(Service):

    class Config:
        private = True

    @private
    def get_pci_vpd(self, pci_addr):
        lspci_cmd = ['lspci', '-vv', '-s', pci_addr]
        ret = subprocess.run(lspci_cmd, capture_output=True)
        if ret.returncode:
            error = ret.stderr.decode() if ret.stderr else ret.stdout.decode()
            if not error:
                error = 'No error message reported'
            self.logger.debug('Failed to execute command: %r with error: %r', " ".join(lspci_cmd), error)
            raise CallError(f'Failed to determine serial number/product: {error}')
        result = {}
        for line in ret.stdout.decode().split('\n'):
            sline = line.strip()
            if sline.startswith(PRODUCT_NAME_PREFIX):
                result['product'] = sline[len(PRODUCT_NAME_PREFIX):]
            elif sline.startswith(SERIAL_NUMBER_PREFIX):
                result['serial'] = sline[len(SERIAL_NUMBER_PREFIX):]
            elif sline.startswith(PART_NUMBER_PREFIX):
                result['part'] = sline[len(PART_NUMBER_PREFIX):]
        return result

    @api_method(RdmaLinkConfigArgs, RdmaLinkConfigResult, private=True)
    async def get_link_choices(self, all):
        """Return a list containing dictionaries with keys 'rdma' and 'netdev'.

        Unless all is set to True, configured interfaces will be excluded."""
        all_links = await self.middleware.call('rdma._get_link_choices')
        if all:
            return all_links

        existing = await self.middleware.call('interface.get_configured_interfaces')
        return list(filter(lambda x: x['netdev'] not in existing, all_links))

    @private
    @cache
    def _get_link_choices(self):
        """Return a list containing dictionaries with keys 'rdma' and 'netdev'.

        Since these are just the hardware present in the system, we cache the result."""
        self.logger.trace('Fetching RDMA link netdev choices')

        link_cmd = ['rdma', '-j', 'link']

        ret = subprocess.run(link_cmd, capture_output=True)
        if ret.returncode:
            error = ret.stderr.decode() if ret.stderr else ret.stdout.decode()
            if not error:
                error = 'No error message reported'
            self.logger.debug('Failed to execute command: %r with error: %r', " ".join(link_cmd), error)
            raise CallError(f'Failed to determine RDMA links: {error}')

        result = []
        for link in json.loads(ret.stdout.decode()):
            if 'netdev' in link:
                result.append({'rdma': link['ifname'], 'netdev': link['netdev']})
        return result

    @api_method(RDMAGetCardChoicesArgs, RDMAGetCardChoicesResult, roles=['NETWORK_INTERFACE_READ'])
    @cache
    def get_card_choices(self):
        """Return a list containing details about each RDMA card.  Dual cards
        will contain two RDMA links."""
        self.logger.info('Fetching RDMA card choices')
        links = self.middleware.call_sync('rdma.get_link_choices', True)
        grouper = {}
        for link in links:
            rdma = link["rdma"]
            p = Path(f'/sys/class/infiniband/{rdma}')
            if not p.is_symlink():
                # Should never happen
                self.logger.debug(f'Not a symlink: {p}')
                continue
            pci_addr = p.readlink().parent.parent.name
            if ':' not in pci_addr:
                # Should never happen
                self.logger.debug(f'{rdma} symlink {p} does not yield a PCI address: {pci_addr}')
                continue
            vpd = self.middleware.call_sync('rdma.get_pci_vpd', pci_addr)
            serial = vpd.get('serial')
            if not serial:
                # Should never happen
                self.logger.debug(f'Could not find serial number for {rdma} / {pci_addr}')
                continue
            part_number = vpd.get('part', '')
            # We'll use part_number:serial as the key, just in case we had different
            # device types with the same serial number (unlikely)
            key = f'{part_number}:{serial}'
            if key not in grouper:
                grouper[key] = {'serial': serial,
                                'product': vpd.get('product', ''),
                                'part_number': part_number,
                                'links': [link]}
            else:
                grouper[key]['links'].append(link)
        # Now that we have finished processing, generate a name that can be used
        # to store in the database.  We will concatenate the rdma names in each
        # card.
        for k, v in grouper.items():
            names = [link['rdma'] for link in v['links']]
            v['name'] = ':'.join(sorted(names))
        return list(grouper.values())

    @api_method(RDMACapableProtocolsArgs, RDMACapableProtocolsResult, roles=['NETWORK_INTERFACE_READ'])
    async def capable_protocols(self):
        result = []
        is_ent = await self.middleware.call('system.is_enterprise')
        if is_ent and 'MINI' not in await self.middleware.call('truenas.get_chassis_hardware'):
            if await self.middleware.call('rdma.get_link_choices', True):
                result.extend([RDMAprotocols.NFS.value, RDMAprotocols.ISER.value, RDMAprotocols.NVMET.value])
        return result
