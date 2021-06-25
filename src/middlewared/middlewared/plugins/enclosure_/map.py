from collections import namedtuple
import re

from middlewared.service import Service, private

ProductMapping = namedtuple("ProductMapping", ["product_re", "mappings"])
VersionMapping = namedtuple("VersionMapping", ["version_re", "slots"])
MappingSlot = namedtuple("MappingSlot", ["num", "slot", "identify"])


MAPPINGS = [
    ProductMapping(re.compile(r"(TRUE|FREE)NAS-MINI-3.0-E\+?$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 4, False),
        ]),
    ]),
    ProductMapping(re.compile(r"(TRUE|FREE)NAS-MINI-3.0-X$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(1, 0, False),
            MappingSlot(1, 1, False),
            MappingSlot(1, 3, False),
        ]),
    ]),
    ProductMapping(re.compile(r"(TRUE|FREE)NAS-MINI-3.0-X\+$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 4, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 6, False),
        ]),
    ]),
    ProductMapping(re.compile(r"(TRUE|FREE)NAS-MINI-3.0-XL\+$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(1, 4, False),
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 4, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 6, False),
            MappingSlot(0, 7, False),
            MappingSlot(1, 3, False),
        ]),
    ]),
]


class EnclosureService(Service):
    @private
    async def map_enclosures(self, enclosures):
        info = await self.middleware.call("system.dmidecode_info")
        if info["system-product-name"] is not None:
            for product_mapping in MAPPINGS:
                if product_mapping.product_re.match(info["system-product-name"]):
                    for version_mapping in product_mapping.mappings:
                        if version_mapping.version_re.match(info["system-version"]):
                            return await self._map_enclosures(enclosures, version_mapping.slots)

        return enclosures

    async def _map_enclosures(self, enclosures, slots):
        elements = []
        has_slot_status = False
        for slot, mapping in enumerate(slots, 1):
            try:
                original_enclosure = enclosures[mapping.num]
            except IndexError:
                self.logger.error("Mapping referenced enclosure %d but it is not present on this system",
                                  mapping.num)
                return []

            original_slots = list(filter(lambda element: element["name"] == "Array Device Slot",
                                         original_enclosure["elements"]))[0]["elements"]

            try:
                original_slot = original_slots[mapping.slot]
            except IndexError:
                self.logger.error("Mapping referenced slot %d in enclosure %d but it is not present on this system",
                                  mapping.slot, mapping.num)
                return []

            element = {
                "slot": slot,
                "data": dict(original_slot["data"], **{
                    "Descriptor": f"Disk #{slot}",
                }),
                "name": "Array Device Slot",
                "descriptor": f"Disk #{slot}",
                "status": original_slot["status"],
                "value": original_slot["value"],
                "value_raw": original_slot["value_raw"],
                "original": {
                    "enclosure_id": original_enclosure["id"],
                    "slot": original_slot["slot"],
                },
            }
            if mapping.identify:
                has_slot_status = True
                for k in ["fault", "identify"]:
                    if k in original_slot:
                        element[k] = original_slot[k]
                    else:
                        self.logger.warning("Mapping referenced slot %d in enclosure %d as identifiable but key %r "
                                            "is not present on this system", mapping.slot, mapping.num, k)
                        has_slot_status = False

            elements.append(element)

        info = await self.middleware.call("system.info")
        return [
            {
                "id": "mapped_enclosure_0",
                "name": "Drive Bays",
                "model": info["system_product"],
                "controller": True,
                "elements": [
                    {
                        "name": "Array Device Slot",
                        "descriptor": "Drive Slots",
                        "header": ["Descriptor", "Status", "Value", "Device"],
                        "elements": elements,
                        "has_slot_status": has_slot_status,
                    },
                ],
            }
        ]
