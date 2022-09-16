import re
from pathlib import Path

from pyudev import Context, Devices, DeviceNotFoundAtPathError

from middlewared.service import Service, private


class EnclosureService(Service):
    RE_NVME = re.compile(r"^nvme[0-9]+$")
    RE_SLOT = re.compile(r"^0-([0-9]+)$")

    @private
    def fake_nvme_enclosure(self, id, name, model, count, slot_to_nvme):
        elements = []
        for slot in range(1, 1 + count):
            device = slot_to_nvme.get(slot, None)

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
                "id": id,
                "name": name,
                "model": model,
                "controller": True,
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
        ctx = Context()
        for i in filter(lambda x: x.attributes.get("path") == b"\\_SB_.PC03.BR3A", ctx.list_devices(subsystem="acpi")):
            try:
                physical_node = Devices.from_path(ctx, f"{i.sys_path}/physical_node")
            except DeviceNotFoundAtPathError:
                # happens when there are no rear-nvme drives plugged in
                pass
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

    @private
    def map_nvme(self, info, acpihandles):
        mapped = info[-1]
        num_of_nvme_slots = info[-2]
        ctx = Context()
        for i in filter(lambda x: x.attributes.get('path') in acpihandles, ctx.list_devices(subsystem='acpi')):
            acpi_handle = i.attributes.get('path')
            try:
                phys_node = Devices.from_path(ctx, f'{i.sys_path}/physical_node')
            except DeviceNotFoundAtPathError:
                return info

            slot = acpihandles[acpi_handle]
            for nvme in filter(lambda x: x.sys_name.startswith('nvme') and x.subsystem == 'block', phys_node.children):
                mapped[slot] = nvme.sys_name
                break
            else:
                mapped[slot] = None

            if len(mapped) == num_of_nvme_slots:
                return info

        return info

    @private
    def r50_nvme_enclosures(self):
        prod = self.middleware.call_sync('system.dmidecode_info')['system-product-name']
        if prod not in ('TRUENAS-R50', 'TRUENAS-R50B'):
            return []

        if prod == 'TRUENAS-R50':
            info = [
                'r50_nvme_enclosure',
                'R50 NVMe Enclosure',
                'R50, Drawer #3',
                3,  # r50 has 3 rear nvme
                {},
            ]
            acpihandles = {b'\\_SB_.PC00.RP01.PXSX': 3, b'\\_SB_.PC01.BR1A.OCL0': 1, b'\\_SB_.PC01.BR1B.OCL1': 2}
        else:
            info = [
                'r50b_nvme_enclosure',
                'R50B NVMe Enclosure',
                'R50B, Drawer #3',
                2,  # r50b has 2 rear nvme
                {},
            ]
            acpihandles = {b'\\_SB_.PC03.BR3A': 2, b'\\_SB_.PC00.RP01.PXSX': 1}

        return self.middleware.call_sync('enclosure.fake_nvme_enclosure', *self.map_nvme(info, acpihandles))
