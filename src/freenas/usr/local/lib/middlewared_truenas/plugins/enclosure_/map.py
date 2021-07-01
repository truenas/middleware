import re
from collections import namedtuple

from middlewared.service import Service, private

ProductMapping = namedtuple("ProductMapping", ["product_re", "mappings"])
VersionMapping = namedtuple("VersionMapping", ["version_re", "slots"])
MappingSlot = namedtuple("MappingSlot", ["num", "slot", "identify"])


MAPPINGS = [
    ProductMapping(re.compile(r"(TRUE|FREE)NAS-MINI-3.0-E$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 4, False),
        ]),
    ]),
    ProductMapping(re.compile(r"(TRUE|FREE)NAS-MINI-3.0-E\+$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
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
            MappingSlot(1, 5, False),
            MappingSlot(0, 0, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
            MappingSlot(0, 3, False),
            MappingSlot(0, 4, False),
            MappingSlot(0, 5, False),
            MappingSlot(0, 6, False),
            MappingSlot(0, 7, False),
            MappingSlot(1, 4, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R10$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(2, 1, False),
            MappingSlot(2, 5, False),
            MappingSlot(2, 9, False),
            MappingSlot(2, 13, False),
            MappingSlot(2, 2, False),
            MappingSlot(2, 6, False),
            MappingSlot(2, 10, False),
            MappingSlot(2, 14, False),
            MappingSlot(2, 3, False),
            MappingSlot(2, 7, False),
            MappingSlot(2, 11, False),
            MappingSlot(2, 15, False),
            MappingSlot(2, 4, False),
            MappingSlot(2, 8, False),
            MappingSlot(2, 12, False),
            MappingSlot(2, 16, False),
        ]),
    ]),
    # R20 and R20B share chassis and mapping
    ProductMapping(re.compile(r"TRUENAS-R20B?$"), [
        VersionMapping(re.compile(".*"), [
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
            MappingSlot(2, 12, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R20A$"), [
        VersionMapping(re.compile(".*"), [
            MappingSlot(2, 3, False),
            MappingSlot(2, 6, False),
            MappingSlot(2, 9, False),
            MappingSlot(2, 12, False),
            MappingSlot(2, 2, False),
            MappingSlot(2, 5, False),
            MappingSlot(2, 8, False),
            MappingSlot(2, 11, False),
            MappingSlot(2, 1, False),
            MappingSlot(2, 4, False),
            MappingSlot(2, 7, False),
            MappingSlot(2, 10, False),
            MappingSlot(0, 1, False),
            MappingSlot(0, 2, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R40$"), [
        VersionMapping(re.compile(".*"), [
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
            MappingSlot(2, 12, False),
            MappingSlot(2, 13, False),
            MappingSlot(2, 14, False),
            MappingSlot(2, 15, False),
            MappingSlot(2, 16, False),
            MappingSlot(2, 17, False),
            MappingSlot(2, 18, False),
            MappingSlot(2, 19, False),
            MappingSlot(2, 20, False),
            MappingSlot(2, 21, False),
            MappingSlot(2, 22, False),
            MappingSlot(2, 23, False),
            MappingSlot(2, 24, False),
            MappingSlot(3, 1, False),
            MappingSlot(3, 2, False),
            MappingSlot(3, 3, False),
            MappingSlot(3, 4, False),
            MappingSlot(3, 5, False),
            MappingSlot(3, 6, False),
            MappingSlot(3, 7, False),
            MappingSlot(3, 8, False),
            MappingSlot(3, 9, False),
            MappingSlot(3, 10, False),
            MappingSlot(3, 11, False),
            MappingSlot(3, 12, False),
            MappingSlot(3, 13, False),
            MappingSlot(3, 14, False),
            MappingSlot(3, 15, False),
            MappingSlot(3, 16, False),
            MappingSlot(3, 17, False),
            MappingSlot(3, 18, False),
            MappingSlot(3, 19, False),
            MappingSlot(3, 20, False),
            MappingSlot(3, 21, False),
            MappingSlot(3, 22, False),
            MappingSlot(3, 23, False),
            MappingSlot(3, 24, False),
        ]),
    ]),
    ProductMapping(re.compile(r"TRUENAS-R50$"), [
        VersionMapping(re.compile(".*"), [
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
            MappingSlot(2, 12, False),
            MappingSlot(2, 13, False),
            MappingSlot(2, 14, False),
            MappingSlot(2, 15, False),
            MappingSlot(2, 16, False),
            MappingSlot(2, 17, False),
            MappingSlot(2, 18, False),
            MappingSlot(2, 19, False),
            MappingSlot(2, 20, False),
            MappingSlot(2, 21, False),
            MappingSlot(2, 22, False),
            MappingSlot(2, 23, False),
            MappingSlot(2, 24, False),
            MappingSlot(3, 1, False),
            MappingSlot(3, 2, False),
            MappingSlot(3, 3, False),
            MappingSlot(3, 4, False),
            MappingSlot(3, 5, False),
            MappingSlot(3, 6, False),
            MappingSlot(3, 7, False),
            MappingSlot(3, 8, False),
            MappingSlot(3, 9, False),
            MappingSlot(3, 10, False),
            MappingSlot(3, 11, False),
            MappingSlot(3, 12, False),
            MappingSlot(3, 13, False),
            MappingSlot(3, 14, False),
            MappingSlot(3, 15, False),
            MappingSlot(3, 16, False),
            MappingSlot(3, 17, False),
            MappingSlot(3, 18, False),
            MappingSlot(3, 19, False),
            MappingSlot(3, 20, False),
            MappingSlot(3, 21, False),
            MappingSlot(3, 22, False),
            MappingSlot(3, 23, False),
            MappingSlot(3, 24, False),
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
]


class EnclosureService(Service):
    @private
    async def map_enclosures(self, enclosures, product, prod_vers):
        if product:
            for product_mapping in MAPPINGS:
                if product_mapping.product_re.match(product):
                    for version_mapping in product_mapping.mappings:
                        if version_mapping.version_re.match(prod_vers):
                            return await self._map_enclosures(enclosures, version_mapping.slots)

        return enclosures

    async def _map_enclosures(self, enclosures, slots):
        mapped = [{
            "id": "mapped_enclosure_0",
            "name": "Drive Bays",
            "model": "",
            "controller": True,
            "has_slot_status": False,
            "elements": {"Array Device Slot": {}},
        }]

        orig_slots = {}
        orig_id = this_num = None
        for slot, mapping in enumerate(slots, 1):
            if mapping.num != this_num:
                # this means we haven't pulled out the original enclosure
                # information for /dev/ses{mapping.num}.
                orig = [i for i in enclosures if i["number"] == mapping.num]
                if not orig:
                    self.logger.error("Failed to detect /dev/ses%d. Mapping enclosure failed.", mapping.num)
                    return []
                else:
                    this_num = mapping.num
                    orig_id = orig[0]["id"]
                    # pull out the original slots
                    orig_slots = orig[0]["elements"]["Array Device Slot"]
                    # set the model of the mapped enclosure
                    mapped[0]["model"] = orig[0]["model"]

            # now we need to map the original enclosures disk slots to the new mapping
            try:
                orig_slot = orig_slots[mapping.slot]
            except IndexError:
                self.logger.error(
                    "Failed to detect slot %d in enclosure /dev/ses%d. Mapping slot failed.", mapping.slot, mapping.num
                )
                return []

            # disk has been mapped so update `mapped` variable appropriately
            mapped[0]["elements"]["Array Device Slot"].update({
                slot: {
                    "descriptor": f"Disk #{slot}",
                    "status": orig_slot["status"],
                    "value": orig_slot["value"],
                    "value_raw": orig_slot["value_raw"],
                    "dev": orig_slot["dev"],
                    "original": {
                        "enclosure_id": orig_id,
                        "slot": mapping.slot,
                    },
                }
            })

            # set this if the disk that is being mapped is flagged
            # as being able to be faulted/identified/cleared etc
            # NOTE: we're doing this wrong....we're not setting this per-disk
            # we're setting this for _ALL_ disks. The only way this will ever
            # be True is if _ALL_ disks were mapped as True up above in the
            # mapping code.....
            mapped[0]["has_slot_status"] = True if mapping.identify else False

        # getting here means we've mapped the enclosures for the given product
        # but if we have future products that need to be mapped and/or have the
        # ability to support expansion shelves, then we need to add them back
        # in here so drive identification works
        mapped.extend([enc for enc in enclosures if not enc["controller"]])

        return mapped
