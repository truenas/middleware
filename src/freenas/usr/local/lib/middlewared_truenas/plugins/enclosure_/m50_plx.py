import re

from middlewared.service import Service, private
from middlewared.utils.osc import IS_FREEBSD

if IS_FREEBSD:
    import sysctl


class EnclosureService(Service):
    RE_PCI = re.compile(r"pci([0-9]+)")
    RE_PCIB = re.compile(r"pcib([0-9]+)")
    RE_SLOT = re.compile(r"slot=([0-9]+)")

    @private
    def m50_plx_enclosures(self):
        system_product = self.middleware.call_sync("system.info")["system_product"]
        if system_product is None or not ("TRUENAS-M50" in system_product or "TRUENAS-M60" in system_product):
            return []

        nvme_to_nvd = self.middleware.call_sync('disk.nvme_to_nvd_map')

        slot_to_nvd = {}
        for nvme, nvd in nvme_to_nvd.items():
            try:
                pci = sysctl.filter(f"dev.nvme.{nvme}.%parent")[0].value
                m = re.match(self.RE_PCI, pci)
                if not m:
                    continue

                pcib = sysctl.filter(f"dev.pci.{m.group(1)}.%parent")[0].value
                m = re.match(self.RE_PCIB, pcib)
                if not m:
                    continue

                pnpinfo = sysctl.filter(f"dev.pcib.{m.group(1)}.%pnpinfo")[0].value
                if "vendor=0x10b5 device=0x8717" not in pnpinfo:
                    continue

                location = sysctl.filter(f"dev.pcib.{m.group(1)}.%location")[0].value
                m = re.match(self.RE_SLOT, location)
                if not m:
                    continue
                slot = int(m.group(1))
            except IndexError:
                continue

            slot_to_nvd[slot] = f"nvd{nvd}"

        return self.middleware.call_sync(
            "enclosure.fake_nvme_enclosure",
            "m50_plx_enclosure",
            "Rear NVME U.2 Hotswap Bays",
            "M50/60 Series",
            4,
            slot_to_nvd
        )
