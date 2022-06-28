import re

import sysctl
from middlewared.service import Service, private


class EnclosureService(Service):
    RE_PCI = re.compile(r'pci([0-9]+)')
    RE_PCIB = re.compile(r'pcib([0-9]+)')

    @private
    def map_nvme(self, product, nvme_slots):
        for nvme, nvd in self.middleware.call_sync('disk.nvme_to_nvd_map', True).items():
            pci = sysctl.filter(f'dev.nvme.{nvme}.%parent')[0].value
            m = re.match(self.RE_PCI, pci)
            if not m:
                continue

            pcib = sysctl.filter(f'dev.pci.{m.group(1)}.%parent')[0].value
            m = re.match(self.RE_PCIB, pcib)
            if not m:
                continue

            pnpinfo = sysctl.filter(f'dev.pcib.{m.group(1)}.%pnpinfo')[0].value
            bridge_ids = ['vendor=0x8086 device=0xa190', 'vendor=0x8086 device=0x2030', 'vendor=0x8086 device=0x2031']
            if not any(string in pnpinfo for string in bridge_ids):
                continue

            try:
                location = sysctl.filter(f'dev.pcib.{m.group(1)}.%location')[0].value
                if product == 'TRUENAS-R50B':
                    if '_SB_.PC03.BR3A' in location:
                        slot = 49
                    elif '_SB_.PC00.RP01' in location:
                        slot = 50
                    else:
                        continue
                elif product == 'TRUENAS-R50':
                    if 'PC01.BR1A.OCL' in location:
                        slot = 49
                    elif 'PC01.BR1B.OCL' in location:
                        slot = 50
                    elif 'PC00.RP01.PXSX' in location:
                        slot = 51
                    else:
                        continue

                nvme_slots[slot] = f'nvd{nvd}'
            except Exception:
                self.logger.error('Failed to map /dev/nvme%s device', nvme, exc_info=True)
                continue

    @private
    def format_nvme_slots(self, nvme_slots):
        elements = {'Array Device Slot': {}}
        for slot, nvme in nvme_slots.items():
            if nvme is not None:
                status = 'OK'
                value_raw = 16777216
                dev = nvme
            else:
                status = 'Not Installed'
                value_raw = 83886080
                dev = ''

            elements['Array Device Slot'][slot] = {
                'descriptor': f'Disk #{slot}',
                'status': status,
                'value': 'None',
                'value_raw': value_raw,
                'dev': dev,
                'original': {
                    'enclosure_id': None,
                    'number': None,
                    'slot': None,
                }
            }

        return elements

    @private
    def rseries_nvme_enclosures(self, product):
        if product == 'TRUENAS-R50':
            nvme_slots = {49: None, 50: None, 51: None}
        elif product == 'TRUENAS-R50B':
            nvme_slots = {49: None, 50: None}
        else:
            # should never get here
            return []

        self.map_nvme(product, nvme_slots)
        return self.format_nvme_slots(nvme_slots)
