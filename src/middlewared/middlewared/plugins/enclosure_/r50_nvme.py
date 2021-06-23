import re

from middlewared.service import Service, private


class EnclosureService(Service):
    RE_HANDLE = re.compile(r"handle=(\S+)")
    HANDLES = {
        r"\_SB_.PC01.BR1A.OCL0": 1,
        r"\_SB_.PC01.BR1B.OCL1": 2,
        r"\_SB_.PC00.RP01.PXSX": 3,
    }

    @private
    def r50_nvme_enclosures(self):
        """
        # TODO: fix on SCALE
        product = self.middleware.call_sync("system.dmidecode_info")["system-product-name"]
        if product != "TRUENAS-R50":
            return []

        nvme_to_nvd = self.middleware.call_sync('disk.nvme_to_nvd_map')

        slot_to_nvd = {}
        for nvme, nvd in nvme_to_nvd.items():
            try:
                location = sysctl.filter(f"dev.nvme.{nvme}.%location")[0].value
                m = re.search(self.RE_HANDLE, location)
                if not m:
                    continue

                handle = m.group(1)
                if handle not in self.HANDLES:
                    continue

                slot = self.HANDLES[handle]
            except IndexError:
                continue

            slot_to_nvd[slot] = f"nvd{nvd}"

        return self.middleware.call_sync(
            "enclosure.fake_nvme_enclosure",
            "r50_nvme_enclosure",
            "R50 NVMe enclosure",
            "R50, Drawer #3",
            3,
            slot_to_nvd
        )
        """
        return []
