import re

from middlewared.service import Service, private
from middlewared.utils.osc import IS_FREEBSD

if IS_FREEBSD:
    from nvme import get_nsid
    import sysctl


class EnclosureService(Service):
    RE_PCI = re.compile(r"pci([0-9]+)")
    RE_PCIB = re.compile(r"pcib([0-9]+)")
    RE_SLOT = re.compile(r"slot=([0-9]+)")

    @private
    def m50_plx_enclosures(self):
        system_product = self.middleware.call_sync("system.info")["system_product"]
        if not ("TRUENAS-M50" in system_product or "TRUENAS-M60" in system_product):
            return []

        nvme_to_nvd = {}
        for disk in self.middleware.call_sync("disk.query", [["devname", "^", "nvd"]]):
            try:
                n = int(disk["devname"][len("nvd"):])
            except ValueError:
                continue
            nvme = get_nsid(f"/dev/{disk['devname']}")
            if nvme is not None:
                nvme_to_nvd[int(nvme[4:])] = n

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

        elements = []
        for slot in range(1, 5):
            device = slot_to_nvd.get(slot, None)

            if device is not None:
                status = "OK"
                value_raw = "0x1000000"
            else:
                status = "Not Installed"
                value_raw = "0x05000000"

            elements.append({
                "slot": slot,
                "data": {
                    "Descriptor": f"Disk #{slot}",
                    "Status": status,
                    "Value": "None",
                    "Device": device,
                },
                "name": "Array Device Slot",
                "descriptor": f"Disk #{slot}",
                "status": status,
                "value": "None",
                "value_raw": value_raw,
            })

        return [
            {
                "id": "m50_plx_enclosure",
                "name": "Rear NVME U.2 Hotswap Bays",
                "model": "M50/60 Series",
                "controller": True,
                "label": "Rear NVME U.2 Hotswap Bays",
                "elements": [
                    {
                        "name": "Array Device Slot",
                        "descriptor": "Drive Slots",
                        "header": ["Descriptor", "Status", "Value", "Device"],
                        "elements": elements,
                        "has_slot_status": False,
                    },
                ],
            }
        ]
