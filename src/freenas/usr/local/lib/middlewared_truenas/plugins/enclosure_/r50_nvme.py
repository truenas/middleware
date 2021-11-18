import re

from middlewared.service import Service, private
import sysctl


class EnclosureService(Service):
    RE_HANDLE = re.compile(r"handle=(\S+)")
    HANDLES = {
        r"\_SB_.PC01.BR1A.OCL0": 1,
        r"\_SB_.PC01.BR1B.OCL1": 2,
        r"\_SB_.PC00.RP01.PXSX": 3,
    }

    @private
    def r50_nvme_enclosures(self):
        system_product = self.middleware.call_sync("system.info")["system_product"]
        if system_product not in ("TRUENAS-R50", "TRUENAS-R50B"):
            return []
        else:
            model = system_product.split("-")[-1].upper()
            if model == "R50B":
                self.HANDLES[r"\_SB_.PC00.RP01.PXSX"] = 1

        slot_to_nvd = {}
        for nvme, nvd in self.middleware.call_sync('disk.nvme_to_nvd_map').items():
            try:
                location = sysctl.filter(f"dev.nvme.{nvme}.%location")[0].value
                m = re.search(self.RE_HANDLE, location)
                if not m and (model == 'R50B' and nvme == 2):
                    # R50B is wired differently than R50 and nvme2 doesn't
                    # have a `handle=` entry in sysctl output so this is
                    # enough information to mark it as slot 2
                    slot = 2
                elif not m:
                    continue
                else:
                    handle = m.group(1)
                    if handle not in self.HANDLES:
                        continue

                    slot = self.HANDLES[handle]
            except IndexError:
                continue

            slot_to_nvd[slot] = f"nvd{nvd}"

        return self.middleware.call_sync(
            "enclosure.fake_nvme_enclosure",
            f"{model.lower()}_nvme_enclosure",
            f"{model} NVMe enclosure",
            f"{model}, Drawer #3",
            3,
            slot_to_nvd
        )
