import re

import sysctl
from middlewared.service import Service, private


class EnclosureService(Service):
    RE_PCI = re.compile(r'pci([0-9]+)')
    RE_PCIB = re.compile(r'pcib([0-9]+)')
    RE_SLOT = re.compile(r'slot=([0-9]+)')

    @private
    def mseries_plx_enclosures(self, product):
        slot_to_nvd = {}
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
            if 'vendor=0x10b5 device=0x8717' not in pnpinfo:
                continue

            location = sysctl.filter(f'dev.pcib.{m.group(1)}.%location')[0].value
            m = re.match(self.RE_SLOT, location)
            if not m:
                continue

            try:
                slot = int(m.group(1))
            except IndexError:
                continue

            slot_to_nvd[slot] = f'nvd{nvd}'

        try:
            model = product.split('-')[1]
        except IndexError:
            # SMBIOS is mistagged so default to 'M50'
            # since the rear NVMe drive bays are the
            # same as the M60 (at time of writing this)
            model = 'M50'

        return self.middleware.call_sync(
            'enclosure.fake_nvme_enclosure',
            f'{model.lower()}_plx_enclosure',
            'Rear NVME U.2 Hotswap Bays',
            f'{model}',
            4,
            slot_to_nvd
        )
