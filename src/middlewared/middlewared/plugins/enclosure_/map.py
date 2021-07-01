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
        VersionMapping(re.compile(r"1\.0"), [
            MappingSlot(1, 0, False),
            MappingSlot(1, 1, False),
            MappingSlot(1, 3, False),
            MappingSlot(1, 4, False),
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
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
    ProductMapping(re.compile(r"TRUENAS-R10$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 4, False),
            MappingSlot(0, 8, False),
            MappingSlot(0, 12, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 9, False),
            MappingSlot(0, 13, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 6, False),
            MappingSlot(0, 10, False),
            MappingSlot(0, 14, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 7, False),
            MappingSlot(0, 11, False),
            MappingSlot(0, 15, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R20A?$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(2, 0, False),
            MappingSlot(2, 1, False),
            MappingSlot(2, 2, False),
            MappingSlot(2, 3, False),
            MappingSlot(2, 4, False),
            MappingSlot(2, 5, False),
            MappingSlot(2, 6, False),
            MappingSlot(2, 7, False),
            MappingSlot(2, 8, False),
            MappingSlot(2, 9, False),
            MappingSlot(2, 10, False),
            MappingSlot(2, 11, False),
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R40$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 4, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 6, False),
            MappingSlot(0, 7, False),
            MappingSlot(0, 8, False),
            MappingSlot(0, 9, False),
            MappingSlot(0, 10, False),
            MappingSlot(0, 11, False),
            MappingSlot(0, 12, False),
            MappingSlot(0, 13, False),
            MappingSlot(0, 14, False),
            MappingSlot(0, 15, False),
            MappingSlot(0, 16, False),
            MappingSlot(0, 17, False),
            MappingSlot(0, 18, False),
            MappingSlot(0, 19, False),
            MappingSlot(0, 20, False),
            MappingSlot(0, 21, False),
            MappingSlot(0, 22, False),
            MappingSlot(0, 23, False),
            MappingSlot(1, 0, False),
            MappingSlot(1, 1, False),
            MappingSlot(1, 2, False),
            MappingSlot(1, 3, False),
            MappingSlot(1, 4, False),
            MappingSlot(1, 5, False),
            MappingSlot(1, 6, False),
            MappingSlot(1, 7, False),
            MappingSlot(1, 8, False),
            MappingSlot(1, 9, False),
            MappingSlot(1, 10, False),
            MappingSlot(1, 11, False),
            MappingSlot(1, 12, False),
            MappingSlot(1, 13, False),
            MappingSlot(1, 14, False),
            MappingSlot(1, 15, False),
            MappingSlot(1, 16, False),
            MappingSlot(1, 17, False),
            MappingSlot(1, 18, False),
            MappingSlot(1, 19, False),
            MappingSlot(1, 20, False),
            MappingSlot(1, 21, False),
            MappingSlot(1, 22, False),
            MappingSlot(1, 23, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R50$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 4, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 6, False),
            MappingSlot(0, 7, False),
            MappingSlot(0, 8, False),
            MappingSlot(0, 9, False),
            MappingSlot(0, 10, False),
            MappingSlot(0, 11, False),
            MappingSlot(0, 12, False),
            MappingSlot(0, 13, False),
            MappingSlot(0, 14, False),
            MappingSlot(0, 15, False),
            MappingSlot(0, 16, False),
            MappingSlot(0, 17, False),
            MappingSlot(0, 18, False),
            MappingSlot(0, 19, False),
            MappingSlot(0, 20, False),
            MappingSlot(0, 21, False),
            MappingSlot(0, 22, False),
            MappingSlot(0, 23, False),
            MappingSlot(1, 0, False),
            MappingSlot(1, 1, False),
            MappingSlot(1, 2, False),
            MappingSlot(1, 3, False),
            MappingSlot(1, 4, False),
            MappingSlot(1, 5, False),
            MappingSlot(1, 6, False),
            MappingSlot(1, 7, False),
            MappingSlot(1, 8, False),
            MappingSlot(1, 9, False),
            MappingSlot(1, 10, False),
            MappingSlot(1, 11, False),
            MappingSlot(1, 12, False),
            MappingSlot(1, 13, False),
            MappingSlot(1, 14, False),
            MappingSlot(1, 15, False),
            MappingSlot(1, 16, False),
            MappingSlot(1, 17, False),
            MappingSlot(1, 18, False),
            MappingSlot(1, 19, False),
            MappingSlot(1, 20, False),
            MappingSlot(1, 21, False),
            MappingSlot(1, 22, False),
            MappingSlot(1, 23, False),
            MappingSlot(2, 0, False),
            MappingSlot(2, 1, False),
            MappingSlot(2, 2, False),
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
        # Ensure JBODs don't effect ordering by filtering them out
        controller_enclosures = list(filter(lambda x: x['controller'], enclosures))
        elements = []
        has_slot_status = False
        for slot, mapping in enumerate(slots, 1):
            try:
                original_enclosure = controller_enclosures[mapping.num]
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

        mapped = [
            {
                "id": "mapped_enclosure_0",
                "name": "Drive Bays",
                "model": controller_enclosures[0]["model"],
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

        # if we have future products that need to be mapped and/or have the
        # ability to support expansion shelves, then we need to add them
        # back in here so drive identification works
        for enclosure in enclosures:
            if not enclosure["controller"]:
                mapped.append(enclosure)

        return mapped
