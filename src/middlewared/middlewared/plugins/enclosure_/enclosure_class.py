import logging

from middlewared.utils.scsi_generic import inquiry
from .identification import get_enclosure_model_and_controller
from .element_types import ELEMENT_TYPES, ELEMENT_DESC
from .sysfs_disks import map_disks_to_enclosure_slots
from .slot_mappings import get_slot_info

logger = logging.getLogger(__name__)


class Enclosure:
    def __init__(self, bsg, sg, dmi, enc_stat):
        self.bsg, self.sg, self.pci, self.dmi = bsg, sg, bsg.removeprefix('/dev/bsg/'), dmi
        self.encid, self.status = enc_stat['id'], list(enc_stat['status'])
        self.vendor, self.product, self.revision, self.encname = self._get_vendor_product_revision_and_encname()
        self.model, self.controller = self._get_model_and_controller()
        self.sysfs_map = map_disks_to_enclosure_slots(self.pci)
        self.disks_map = self._get_array_device_mapping_info()
        self.elements = self._parse_elements(enc_stat['elements'])

    def asdict(self):
        """This method is what is returned in enclosure2.query"""
        return {
            'name': self.encname,  # vendor, product and revision joined by whitespace
            'model': self.model,  # M60, F100, MINI-R, etc
            'controller': self.controller,  # if True, represents the "head-unit"
            'dmi': self.dmi,  # comes from system.dmidecode_info[system-product-name]
            'status': self.status,  # the overall status reported by the enclosure
            'id': self.encid,
            'vendor': self.vendor,  # t10 vendor from INQUIRY
            'product': self.product,  # product from INQUIRY
            'revision': self.revision,  # revision from INQUIRY
            'bsg': self.bsg,  # the path for which this maps to a bsg device (/dev/bsg/0:0:0:0)
            'sg': self.sg,  # the scsi generic device (/dev/sg0)
            'pci': self.pci,  # the pci info (0:0:0:0)
            'elements': self.elements  # dictionary with all element types and their relevant information
        }

    def _get_vendor_product_revision_and_encname(self):
        """Sends a standard INQUIRY command to the enclosure device
        so we can parse the vendor/prodcut/revision(and /serial if we ever wanted
        to use that information) for the enclosure device. It's important
        that we parse this information into their own top-level keys since we
        base some of our drive mappings (potentially) on the "revision" (aka firmware)
        for the enclosure
        """
        inq = inquiry(self.sg)
        data = [inq['vendor'], inq['product'], inq['revision']]
        data.append(' '.join(data))
        return data

    def _get_model_and_controller(self):
        key = f'{self.vendor}_{self.product}'
        return get_enclosure_model_and_controller(key, self.dmi)

    def _ignore_element(self, parsed_element_status, element):
        """We ignore certain elements reported by the enclosure, for example,
        elements that report as unsupported. Our alert system polls enclosures
        for elements that report "bad" statuses and these elements need to be
        ignored. NOTE: every hardware platform is different for knowing which
        elements are to be ignored"""
        if parsed_element_status == 'Unsupported':
            return True
        elif self.model in ('X10', 'X20'):
            return element['descriptor'] == 'ArrayDevicesInSubEnclsr0'
        elif self.model == 'ES60':
            return element['descriptor'] == 'Array Device Slot'
        elif self.model not in ('H10', 'H20'):
            # On the H10/20 platforms, the onboard HBA reports null descriptors
            # for every single array device. The sg3_utils API returns a literal
            # "<empty>" string. On the H10/20, these are legit elements but we
            # have other platforms that return null descriptor values but they
            # are invalid
            return element['descriptor'] in ('<empty>', 'ArrayDevices', 'Drive Slots')

    def _get_array_device_mapping_info(self):
        mapped_info = get_slot_info(self.model)
        if not mapped_info:
            return

        # we've gotten the disk mapping information based on the
        # enclosure but we need to check if this enclosure has
        # different revisions
        vers_key = 'DEFAULT'
        if not mapped_info['any_version']:
            for key, vers in mapped_info['versions'].items():
                if self.revision == key:
                    vers_key = vers
                    break

        # Now we need to check this specific enclosure's disk slot
        # mapping information
        ids = list()
        if f'{self.vendor}_{self.product}' == 'AHCI_SGPIOEnclosure':
            if self.model.startswith(('R20', 'MINI-')):
                ids.append(('id', self.encid))
        else:
            ids.append(('model', self.model))

        # Now we know the specific enclosure we're on and the specific
        # key we need to use to pull out the drive slot mapping
        for idkey, idvalue in ids:
            for mapkey, mapslots in mapped_info['versions'][vers_key].items():
                if mapkey == idkey and (found := mapslots.get(idvalue)):
                    return found

    def _parse_elements(self, elements):
        final = {}
        for slot, element in elements.items():
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

            if self._ignore_element(element_status, element):
                continue

            if element_type[0] not in final:
                # first time seeing this element type so add it
                final[element_type[0]] = {}

            # convert list of integers representing the elements
            # raw status to an integer so it can be converted
            # appropriately based on the element type
            value_raw = 0
            for val in element['status']:
                value_raw = (value_raw << 8) + val

            mapped_slot = slot
            parsed = {
                'descriptor': element['descriptor'].strip(),
                'status': element_status,
                'value': element_type[1](value_raw),
                'value_raw': value_raw,
            }
            if element_type[0] == 'Array Device Slot' and self.disks_map:
                try:
                    parsed['dev'] = self.sysfs_map[self.disks_map[slot]['sysfs_slot']]
                except KeyError:
                    # this happens on some of the MINI platforms, for example,
                    # the MINI-3.0-XL+ because we map the 1st drive and only
                    # the 1st drive from the Virtual AHCI controller with id
                    # that ends with 002. However, we send a standard enclosure
                    # diagnostics command so all the other elements will return
                    continue

                mapped_slot = self.disks_map[slot]['mapped_slot']
                parsed['original'] = {
                    'enclosure_id': self.encid,
                    'enclosure_sg': self.sg,
                    'enclosure_bsg': self.bsg,
                    'descriptor': f'slot{slot}',
                    'slot': slot,
                }

            final[element_type[0]].update({mapped_slot: parsed})

        return final
