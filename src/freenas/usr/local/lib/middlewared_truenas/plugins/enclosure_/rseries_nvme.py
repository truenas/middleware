import sysctl
from middlewared.service import Service, private


class EnclosureService(Service):
    @private
    def rseries_nvme_enclosures(self, product):
        slot_to_nvd = {}
        for nvme, nvd in self.middleware.call_sync('disk.nvme_to_nvd_map', True).items():
            try:
                location = sysctl.filter(f'dev.nvme.{nvme}.%location')[0].value
                if 'PC01.BR1A.OCL' in location:
                    slot = 1
                elif 'PC01.BR1B.OCL' in location:
                    slot = 2
                elif 'PC00.RP01.PXSX' in location:
                    slot = 3
                else:
                    continue
                slot_to_nvd[slot] = f'nvd{nvd}'
            except Exception:
                self.logger.error('Failed to map /dev/nvme%s device', nvme, exc_info=True)
                continue

        try:
            model = product.split('-')[1]
        except IndexError:
            # SMBIOS is mistagged so default to 'R50'
            # since (at the time of writing this) is
            # the only r-series hardware that has an
            # nvme enclosure
            model = 'R50'

        return self.middleware.call_sync(
            'enclosure.fake_nvme_enclosure',
            f'{model.lower()}_nvme_enclosure',
            f'{model} NVMe enclosure',
            f'{model}',
            3,
            slot_to_nvd
        )
