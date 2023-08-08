import logging
import pathlib

from middlewared.utils.scsi_generic import inquiry
from .identification import get_enclosure_model_and_controller
from .element_types import ELEMENT_TYPES, ELEMENT_DESC


logger = logging.getLogger(__name__)


class Enclosure:
    def __init__(self, bsg, sg, dmi, enc_stat):
        self.bsg, self.sg, self.pci, self.dmi = bsg, sg, bsg.removeprefix('/dev/bsg/'), dmi
        self.encid, self.status = enc_stat['id'], list(enc_stat['status'])
        self.vendor, self.product, self.revision, self.encname = self._get_vendor_product_revision_and_encname()
        self.model, self.controller = self._get_model_and_controller()
        self.elements = self._parse_elements(enc_stat['elements'])

    def asdict(self):
        return {
            'name': self.encname,
            'model': self.model,
            'controller': self.controller,
            'dmi': self.dmi,
            'status': self.status,
            'id': self.encid,
            'vendor': self.vendor,
            'product': self.product,
            'revision': self.revision,
            'bsg': self.bsg,
            'sg': self.sg,
            'pci': self.pci,
            'elements': self.elements
        }

    def _get_vendor_product_revision_and_encname(self):
        inq = inquiry(self.sg)
        data = [inq['vendor'], inq['product'], inq['revision']]
        data.append(' '.join(data))
        return data

    def _get_model_and_controller(self):
        key = f'{self.vendor}_{self.product}'
        return get_enclosure_model_and_controller(key, self.dmi)

    def _map_disks_to_enclosure_slots(self):
        """
        The sysfs directory structure is dynamic based on the enclosure that
        is attached.
        Here are some examples of what we've seen on internal hardware:
            /sys/class/enclosure/19:0:6:0/SLOT_001/
            /sys/class/enclosure/13:0:0:0/Drive Slot #0_0000000000000000/
            /sys/class/enclosure/13:0:0:0/Disk #00/
            /sys/class/enclosure/13:0:0:0/Slot 00/
            /sys/class/enclosure/13:0:0:0/slot00/

        The safe assumption that we can make on whether or not the directory
        represents a drive slot is looking for the file named "slot" underneath
        each directory. (i.e. /sys/class/enclosure/13:0:0:0/Disk #00/slot)

        If this file doesn't exist, it means 1 thing
            1. this isn't a drive slot directory

        Once we've determined that there is a file named "slot", we can read the
        contents of that file to get the slot number associated to the disk device.
        The "slot" file is always an integer so we don't need to convert to hexadecimal.
        """
        mapping = dict()
        for i in filter(lambda x: x.is_dir(), pathlib.Path(f'/sys/class/enclosure/{self.pci}').iterdir()):
            try:
                slot = int((i / 'slot').read_text().strip())
            except (FileNotFoundError, ValueError):
                # not a slot directory
                continue
            else:
                try:
                    dev = next((i / 'device/block').iterdir(), None)
                    mapping[slot] = dev.name if dev is not None else ''
                except FileNotFoundError:
                    # no disk in this slot
                    mapping[slot] = ''
        try:
            # we have a single enclosure (at time of writing this) that enumerates
            # sysfs drive slots starting at number 1 while every other JBOD
            # (and head-units) enumerate syfs drive slots starting at number 0
            min_slot = min(mapping)
        except ValueError:
            min_slot = 0

        return min_slot, mapping

    def _elements_to_ignore(self, element):
        return element['descriptor'] in ('<empty>', 'ArrayDevices', 'Drive Slots')

    def _parse_elements(self, elements):
        final = {}
        min_slot, disk_map = self._map_disks_to_enclosure_slots()
        for slot, element in filter(lambda x: not self._elements_to_ignore(x[1]), elements.items()):
            try:
                element_type = ELEMENT_TYPES[element['type']]
            except KeyError:
                # means the element type that's being
                # reported to us is unknown so log it
                # and continue on
                logger.warning('Unknown element type: %r for %r', element['type'], self.devname)
                continue

            try:
                element_status = ELEMENT_DESC[element['status'][0]]
            except KeyError:
                # means the elements status reported by the enclosure
                # is not mapped so just report unknown
                element_status = 'UNKNOWN'

            if element_type[0] not in final:
                # first time seeing this element type so add it
                final[element_type[0]] = {}

            # convert list of integers representing the elements
            # raw status to an integer so it can be converted
            # appropriately based on the element type
            value_raw = 0
            for val in element['status']:
                value_raw = (value_raw << 8) + val

            parsed = {slot: {
                'descriptor': element['descriptor'].strip(),
                'status': element_status,
                'value': element_type[1](value_raw),
                'value_raw': value_raw,
            }}
            if element_type[0] == 'Array Device Slot':
                parsed[slot]['dev'] = None
                orig_slot = slot - 1 if min_slot == 0 else slot
                if (disk_dev := disk_map.get(orig_slot, False)):
                    parsed[slot]['dev'] = disk_dev

            final[element_type[0]].update(parsed)

        return final
