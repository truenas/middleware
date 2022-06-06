from pathlib import Path
import re

import pyudev

from middlewared.service import Service, private


class EnclosureService(Service):
    RE_NVME = re.compile(r"^nvme[0-9]+$")
    RE_SLOT = re.compile(r"^0-([0-9]+)$")

    @private
    def m_series_nvme_enclosures(self):
        product = self.middleware.call_sync("system.dmidecode_info")["system-product-name"]
        if product is None or not ("TRUENAS-M50" in product or "TRUENAS-M60" in product):
            return []

        enclosure_id = f"{product.split('-')[1].lower()}_plx_enclosure"
        enclosure_model = f"{product.split('-')[1]} Series"

        addresses_to_slots = {
            (slot / "address").read_text().strip(): slot.name
            for slot in Path("/sys/bus/pci/slots").iterdir()
        }

        slot_to_nvme = {}
        context = pyudev.Context()
        for i in filter(lambda x: x.attributes.get("path") == b"\\_SB_.PC03.BR3A",
                        context.list_devices(subsystem="acpi")):
            physical_node_path = f"{i.sys_path}/physical_node"
            try:
                physical_node = pyudev.Devices.from_path(context, physical_node_path)
            except pyudev.DeviceNotFoundAtPathError:
                self.logger.error("Failed to find PCI slot information for rear NVME drives at path %r",
                                  physical_node_path)
                return []
            else:
                for child in physical_node.children:
                    if not self.RE_NVME.fullmatch(child.sys_name):
                        continue

                    if (slot := addresses_to_slots.get(child.parent.sys_name.split(".")[0])) is None:
                        continue

                    if not (m := re.match(self.RE_SLOT, slot)):
                        continue

                    slot_to_nvme[int(m.group(1))] = child.sys_name

        return self.middleware.call_sync(
            "enclosure.fake_nvme_enclosure",
            enclosure_id,
            "Rear NVME U.2 Hotswap Bays",
            enclosure_model,
            4,
            slot_to_nvme
        )
