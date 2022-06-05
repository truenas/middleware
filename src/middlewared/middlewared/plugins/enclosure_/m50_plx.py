from pathlib import Path
import re

import pyudev

from middlewared.service import Service, private


class EnclosureService(Service):
    RE_SLOT = re.compile(r"^0-([0-9]+)$")

    @private
    def m50_plx_enclosures(self):
        product = self.middleware.call_sync("system.dmidecode_info")["system-product-name"]
        if product is None or not ("TRUENAS-M50" in product or "TRUENAS-M60" in product):
            return []

        addresses_to_slots = {
            (slot / "address").read_text().strip(): slot.name
            for slot in Path("/sys/bus/pci/slots").iterdir()
        }

        slot_to_nvme = {}
        context = pyudev.Context()
        for nvme_device in context.list_devices(subsystem="nvme"):
            controller_path = Path(nvme_device["DEVPATH"]).parent.parent

            port = pyudev.Devices.from_path(context, str(controller_path.parent))
            if port.get("PCI_SUBSYS_ID") != "10B5:8717":
                continue

            slot_address = controller_path.name.split(".")[0]
            if (slot := addresses_to_slots.get(slot_address)) is None:
                continue

            if not (m := re.match(self.RE_SLOT, slot)):
                continue

            slot_to_nvme[int(m.group(1))] = Path(nvme_device["DEVNAME"]).name

        return self.middleware.call_sync(
            "enclosure.fake_nvme_enclosure",
            "m50_plx_enclosure",
            "Rear NVME U.2 Hotswap Bays",
            "M50/60 Series",
            4,
            slot_to_nvme
        )
