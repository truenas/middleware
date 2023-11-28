import json
import subprocess
from pathlib import Path

from middlewared.schema import Dict, List, Ref, Str, accepts, returns
from middlewared.service import Service, private
from middlewared.service_exception import CallError
from middlewared.utils.functools import cache
from middlewared.plugins.rdma.interface import RDMAInterfaceService  # noqa (just import to start the service)

PRODUCT_NAME_PREFIX = 'Product Name: '
SERIAL_NUMBER_PREFIX = '[SN] Serial number: '
PART_NUMBER_PREFIX = '[PN] Part number: '


class RDMAService(Service):

    class Config:
        private = True

    @private
    def get_pci_vpd(self, pci_addr):
        lspci_cmd = ['lspci', '-vv', '-s', pci_addr]
        ret = subprocess.run(lspci_cmd, capture_output=True)
        if ret.returncode:
            self.logger.debug(f'Failed to execute "{" ".join(lspci_cmd)}": {ret.stderr.decode()}')
            raise CallError(f'Failed to determine serial number/product: {ret.stderr.decode()}')
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

    @private
    @accepts()
    @returns(List(items=[Dict(
        'rdma_link_config',
        Str('rdma', required=True),
        Str('netdev', required=True),
        register=True
    )]))
    @cache
    def get_link_choices(self):
        """Return a list containing dictionaries with keys 'rdma' and 'netdev'.

        Since these are just the hardware present in the system, we cache the result."""
        self.logger.info('Fetching RDMA link netdev choices')

        link_cmd = ['rdma', '-j', 'link']

        ret = subprocess.run(link_cmd, capture_output=True)
        if ret.returncode:
            self.logger.debug(f'Failed to execute "{" ".join(link_cmd)}": {ret.stderr.decode()}')
            raise CallError(f'Failed to determine RDMA links: {ret.stderr.decode()}')

        result = []
        for link in json.loads(ret.stdout.decode()):
            result.append({'rdma': link['ifname'], 'netdev': link['netdev']})
        return result

    @accepts()
    @returns(List(items=[Dict(
        'rdma_card_config',
        Str('serial'),
        Str('product'),
        Str('part_number'),
        List('links', items=[Ref('rdma_link_config')])
    )], register=True))
    @cache
    def get_card_choices(self):
        """Return a list containing details about each RDMA card.  Dual cards
        will contain two RDMA links."""
        self.logger.info('Fetching RDMA card choices')
        links = self.middleware.call_sync('rdma.get_link_choices')
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
