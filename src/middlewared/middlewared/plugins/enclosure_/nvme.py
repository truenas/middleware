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
    def map_plx_nvme_impl(self, prod):
        enc_name = prod.split('-')[1]
        enclosure_id = f"{enc_name.lower()}_plx_enclosure"
        enclosure_model = f"{enc_name} Series"
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

        return [
            enclosure_id,
            'Rear NVME U.2 Hotswap Bays',
            enclosure_model,
            4,  # nvme plx bridge used on m50/60 and r50bm have 4 nvme drive bays
            slot_to_nvme
        ]

    @private
    def map_plx_nvme(self, prod):
        return self.fake_nvme_enclosure(*self.map_plx_nvme_impl(prod))

    @private
    def map_r50_or_r50b_impl(self, info, acpihandles):
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
    def map_r50_or_r50b(self, prod):
        if prod.endswith('R50'):
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

        return self.fake_nvme_enclosure(*self.map_r50_or_r50b_impl(info, acpihandles))

    @private
    def map_nvme(self):
        prod = self.middleware.call_sync('system.dmidecode_info')['system-product-name']
        if not prod.endswith(('R50', 'R50B', 'R50BM', 'M50', 'M60')):
            return []

        if prod.endswith(('R50', 'R50B')):
            return self.map_r50_or_r50b(prod)
        else:
            # M50/60 and R50BM use same plx nvme bridge
            return self.map_plx_nvme(prod)
