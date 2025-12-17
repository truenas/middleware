# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import logging
from typing import Literal, TypeAlias, TypedDict

from middlewared.utils.scsi_generic import inquiry

from ixhardware import parse_dmi
from .constants import (
    MINI_MODEL_BASE,
    MINIR_MODEL_BASE,
    SYSFS_SLOT_KEY,
    MAPPED_SLOT_KEY,
    SUPPORTS_IDENTIFY_KEY,
    SUPPORTS_IDENTIFY_STATUS_KEY,
    DISK_FRONT_KEY,
    DISK_REAR_KEY,
    DISK_TOP_KEY,
    DISK_INTERNAL_KEY,
    DRIVE_BAY_LIGHT_STATUS,
)
from .element_types import ELEMENT_TYPES, ELEMENT_DESC
from .enums import ControllerModels, ElementDescriptorsToIgnore, ElementStatusesToIgnore, JbodModels
from .sysfs_disks import map_disks_to_enclosure_slots
from .slot_mappings import get_slot_info

logger = logging.getLogger(__name__)


class EnclosureElementDict(TypedDict):
    type: int
    descriptor: str
    status: list[int]


EnclosureStatus: TypeAlias = Literal['OK', 'INVOP', 'INFO', 'NON-CRIT', 'CRIT', 'UNRECOV']
ElementsDict: TypeAlias = dict[int, EnclosureElementDict]


class EnclosureStatusDict(TypedDict):
    id: str
    name: str
    status: set[EnclosureStatus]
    elements: ElementsDict


class Enclosure:
    def __init__(self, bsg: str, sg: str, enc_stat: EnclosureStatusDict):
        self.dmi = parse_dmi()
        self.bsg, self.sg, self.pci, = bsg, sg, bsg.removeprefix('/dev/bsg/')
        self.encid, self.status = enc_stat['id'], list(enc_stat['status'])
        self.vendor, self.product, self.revision, self.encname = self._get_vendor_product_revision_and_encname()
        self._get_model_and_controller()
        self._should_ignore_enclosure()
        self.sysfs_map, self.disks_map, self.elements = dict(), dict(), dict()

    def initialize(self, elements: ElementsDict, slot_designation: str | None = None):
        if not self.should_ignore:
            self.sysfs_map = map_disks_to_enclosure_slots(self)
            self.disks_map = self._get_array_device_mapping_info(slot_designation)
            self.elements = self._parse_elements(elements)
        return self

    def asdict(self):
        """This method is what is returned in enclosure2.query"""
        return {
            'should_ignore': self.should_ignore,  # enclosure device we dont need or expect
            'name': self.encname,  # vendor, product and revision joined by whitespace
            'model': self.model,  # M60, F100, MINI-R, etc
            'controller': self.controller,  # if True, represents the "head-unit"
            'dmi': self.dmi.system_product_name,
            'status': self.status,  # the overall status reported by the enclosure
            'id': self.encid,
            'vendor': self.vendor,  # t10 vendor from INQUIRY
            'product': self.product,  # product from INQUIRY
            'revision': self.revision,  # revision from INQUIRY
            'bsg': self.bsg,  # the path for which this maps to a bsg device (/dev/bsg/0:0:0:0)
            'sg': self.sg,  # the scsi generic device (/dev/sg0)
            'pci': self.pci,  # the pci info (0:0:0:0)
            'rackmount': self.rackmount,  # requested by UI team
            'top_loaded': self.top_loaded,  # requested by UI team
            'top_slots': self.top_slots,  # requested by UI team
            'front_loaded': self.front_loaded,  # requested by UI team
            'front_slots': self.front_slots,  # requested by UI team
            'rear_slots': self.rear_slots,  # requested by UI team
            'internal_slots': self.internal_slots,  # requested by UI team
            'elements': self.elements  # dictionary with all element types and their relevant information
        }

    def _should_ignore_enclosure(self):
        if not self.model:
            # being unable to determine the model means many other things will not work
            self.should_ignore = True
        elif all((
            (not any((self.is_r20_series, self.is_mini))),
            self.vendor == 'AHCI',
            self.product == 'SGPIOEnclosure',
        )):
            # if this isn't an R20 or MINI platform and this is the Virtual AHCI
            # enclosure, then we can ignore them
            self.should_ignore = True
        elif self.encid == '3000000000000002' and any((
            self.is_r20_series,
            (self.model in (
                ControllerModels.MINI3XP.value,
                ControllerModels.MINI3E.value,
            )),
        )):
            # If this platform is a R20*, a MINI-3.0-X+, or MINI-3.0-E, there are
            # 2x Virtual AHCI enclosure devices. However, the physical drive slots
            # only get mapped to the Virtual AHCI enclosure of the 1st one. (i.e.
            # the one whose enclosure id is "3000000000000001"). So we ignore the
            # other enclosure device otherwise.
            self.should_ignore = True
        elif self.is_vseries and self.vendor == 'ECStream':
            self.should_ignore = True
        else:
            self.should_ignore = False

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
        """This determines the model and whether or not this a controller enclosure.
        The term "controller" refers to the enclosure device where the TrueNAS OS
        is installed (sometimes referred to as the head-unit). We check 2 different
        values to determine the model/controller.

        1. We check SMBIOS DMI type "system" buffer, specifically the product name
        2. We check the t10 vendor and product strings returned from the enclosure
            using a standard inquiry command
        """
        spn = self.dmi.system_product_name
        model = spn.removeprefix('TRUENAS-').removeprefix('FREENAS-')
        for suffix in ('-HA', '-S', '-PC', '-SC', '-C'):
            # "-PC", "-SC", and "-C" are used on R60 platform
            model = model.removesuffix(suffix)

        try:
            dmi_model = ControllerModels[model]
        except KeyError:
            try:
                # the member names of this enum just so happen to line
                # up with the string we get from DMI, however, the MINIs
                # get flashed with strings that have invalid characters
                # for members of an enum. If we get here, then we change
                # to using the parenthesis approach because that matches
                # an entry in the enum by value
                dmi_model = ControllerModels(model)
            except ValueError:
                # this shouldn't ever happen because the instantiator of this class
                # checks DMI before we even get here but better safe than sorry
                logger.warning('Unexpected model: %r from dmi: %r', model, spn)
                self.model = ''
                self.controller = False
                return

        t10vendor_product = f'{self.vendor}_{self.product}'
        match t10vendor_product:
            case 'ECStream_4024Sp' | 'ECStream_4024Ss' | 'iX_4024Sp' | 'iX_4024Ss':
                # M series
                self.model = dmi_model.value
                self.controller = True
            case 'ECStream_4IXGA-NTBp' | 'ECStream_4IXGA-NTBs':
                # V series
                self.model = dmi_model.value
                self.controller = True
            case 'CELESTIC_P3215-O' | 'CELESTIC_P3217-B':
                # X series
                self.model = dmi_model.value
                self.controller = True
            case 'BROADCOM_VirtualSES':
                # H series, V series
                self.model = dmi_model.value
                self.controller = True
            case 'ECStream_FS1' | 'ECStream_FS2' | 'ECStream_DSS212Sp' | 'ECStream_DSS212Ss':
                # R series
                self.model = dmi_model.value
                self.controller = True
            case 'iX_FS1L' | 'iX_FS2' | 'iX_DSS212Sp' | 'iX_DSS212Ss':
                # more R series
                self.model = dmi_model.value
                self.controller = True
            case 'iX_TrueNASR20p' | 'SMC_SC826-P' | 'iX_2012Sp' | 'iX_TrueNASSMCSC826-P':
                # R20 series
                self.model = dmi_model.value
                self.controller = True
            case 'AHCI_SGPIOEnclosure':
                # R20 variants or MINIs
                self.model = dmi_model.value
                self.controller = True
            case 'iX_eDrawer4048S1' | 'iX_eDrawer4048S2':
                # R50
                self.model = dmi_model.value
                self.controller = True
            case 'CELESTIC_X2012' | 'CELESTIC_X2012-MT':
                self.model = JbodModels.ES12.value
                self.controller = False
            case x if x.startswith(('ECStream_4024J', 'iX_4024J')):
                self.model = JbodModels.ES24.value
                self.controller = False
            case 'ECStream_2024Jp' | 'ECStream_2024Js' | 'iX_2024Jp' | 'iX_2024Js':
                self.model = JbodModels.ES24F.value
                self.controller = False
            case 'CELESTIC_R0904-F0001-01' | 'CELESTIC_R0904-F1001-01':
                self.model = JbodModels.ES60.value
                self.controller = False
            case 'HGST_H4060-J':
                self.model = JbodModels.ES60G2.value
                self.controller = False
            case 'WDC_UData60':
                self.model = JbodModels.ES60G3.value
                self.controller = False
            case 'HGST_H4102-J':
                self.model = JbodModels.ES102.value
                self.controller = False
            case 'VikingES_NDS-41022-BB' | 'VikingES_VDS-41022-BB':
                self.model = JbodModels.ES102G2.value
                self.controller = False
            case _:
                logger.warning(
                    'Unexpected t10 vendor: %r and product: %r combination',
                    self.vendor, self.product
                )
                self.model = ''
                self.controller = False

    def _ignore_element(self, parsed_element_status, element):
        """We ignore certain elements reported by the enclosure, for example,
        elements that report as unsupported. Our alert system polls enclosures
        for elements that report "bad" statuses and these elements need to be
        ignored. NOTE: every hardware platform is different for knowing which
        elements are to be ignored"""
        desc = element['descriptor'].lower()
        return any((
            (parsed_element_status.lower() == ElementStatusesToIgnore.UNSUPPORTED.value),
            (self.is_xseries and desc == ElementDescriptorsToIgnore.ADISE0.value),
            (self.model == JbodModels.ES60.value and desc == ElementDescriptorsToIgnore.ADS.value),
            (
                not self.is_hseries
                # Array Device Slot elements' descriptors on V-series are "<empty>"
                and not (self.is_vseries and element['type'] == 23)
                and desc in (
                    ElementDescriptorsToIgnore.EMPTY.value,
                    ElementDescriptorsToIgnore.AD.value,
                    ElementDescriptorsToIgnore.DS.value,
                )
            ),
        ))

    def _get_array_device_mapping_info(self, slot_designation: str | None = None):
        mapped_info = get_slot_info(self)
        if not mapped_info:
            return

        # we've gotten the disk mapping information based on the
        # enclosure but we need to check if this enclosure has
        # different revisions
        vers_key = 'DEFAULT'
        if not mapped_info['any_version']:
            for vers in mapped_info['versions']:
                if self.dmi.system_version == vers:
                    vers_key = vers
                    break

        # Now we need to check this specific enclosure's disk slot
        # mapping information
        if slot_designation:
            idkey, idvalue = 'id', slot_designation
        elif (
            self.vendor == 'AHCI'
            and self.product == 'SGPIOEnclosure'
            and (self.is_mini or self.is_r20_series)
        ):
            idkey, idvalue = 'id', self.encid
        elif self.is_r50_series:
            idkey, idvalue = 'product', self.product
        else:
            idkey, idvalue = 'model', self.model

        # Now we know the specific enclosure we're on and the specific
        # key we need to use to pull out the drive slot mapping
        for mapkey, mapslots in mapped_info['versions'][vers_key].items():
            if mapkey == idkey and (found := mapslots.get(idvalue)):
                return found

    def _parse_elements(self, elements):
        final = {}
        disk_position_mapping = self.determine_disk_slot_positions()
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
                    dinfo = self.disks_map[slot]
                    sysfs_slot = dinfo[SYSFS_SLOT_KEY]
                    parsed['dev'] = self.sysfs_map[sysfs_slot].name
                except KeyError:
                    # this happens on some of the MINI platforms, for example,
                    # the MINI-3.0-XL+ because we map the 1st drive and only
                    # the 1st drive from the Virtual AHCI controller with id
                    # that ends with 002. However, we send a standard enclosure
                    # diagnostics command so all the other elements will return
                    continue

                # does this enclosure slot support identification? (i.e. lighting up LED)
                parsed[SUPPORTS_IDENTIFY_KEY] = dinfo[SUPPORTS_IDENTIFY_KEY]

                # does this enclosure slot support reporting identification status?
                # (i.e. whether the LED is currently lit up)
                if dinfo.get(SUPPORTS_IDENTIFY_STATUS_KEY, parsed[SUPPORTS_IDENTIFY_KEY]):
                    parsed[DRIVE_BAY_LIGHT_STATUS] = self.sysfs_map[sysfs_slot].locate
                else:
                    parsed[DRIVE_BAY_LIGHT_STATUS] = None

                mapped_slot = dinfo[MAPPED_SLOT_KEY]
                # is this a front, rear or internal slot?
                parsed.update(disk_position_mapping.get(mapped_slot, dict()))

                parsed['original'] = {
                    'enclosure_id': self.encid,
                    'enclosure_sg': self.sg,
                    'enclosure_bsg': self.bsg,
                    'descriptor': f'slot{sysfs_slot}',
                    'slot': sysfs_slot,
                }

            final[element_type[0]].update({mapped_slot: parsed})

        return final

    @property
    def model(self):
        return self.__model

    @model.setter
    def model(self, val):
        self.__model = val

    @property
    def controller(self):
        return self.__controller

    @controller.setter
    def controller(self, val):
        self.__controller = val

    @property
    def should_ignore(self):
        """This property serves as an easy way to determine if the enclosure
        that we're parsing meets a certain set of criteria. If the criteria
        is not met, then we set this value to False so that we can short-circuit
        some of the parsing logic as well as provide a value to any caller of
        this class to more easily apply filters as necessary.
        """
        return self.__ignore

    @should_ignore.setter
    def should_ignore(self, val):
        self.__ignore = val

    @property
    def is_jbod(self):
        """Determine if the enclosure device is a JBOD
        (just a bunch of disks) unit.

        Args:
        Returns: bool
        """
        return self.model in (i.value for i in JbodModels)

    @property
    def is_rseries(self):
        """Determine if the enclosure device is a r-series controller.

        Args:
        Returns: bool
        """
        return all((self.controller, self.model and self.model[0] == 'R'))

    @property
    def is_r10(self):
        """Determine if the enclosure device is a r10 controller.

        Args:
        Returns: bool
        """
        return all((
            self.is_rseries,
            (self.model == ControllerModels.R10.value),
        ))

    @property
    def is_r20_series(self):
        """Determine if the enclosure device is a r20-series controller.

        Args:
        Returns: bool
        """
        return all((
            self.is_rseries,
            self.model.startswith((
                ControllerModels.R20.value,
                ControllerModels.R20A.value,
                ControllerModels.R20B.value,
            ))
        ))

    @property
    def is_r30(self):
        """Determine if the enclosure device is a r30 controller.

        Args:
        Returns: bool
        """
        return all((
            self.is_rseries,
            (self.model == ControllerModels.R30.value),
        ))

    @property
    def is_r40(self):
        """Determine if the enclosure device is a r40 controller.

        Args:
        Returns: bool
        """
        return all((
            self.is_rseries,
            (self.model == ControllerModels.R40.value),
        ))

    @property
    def is_r50_series(self):
        """Determine if the enclosure device is a r50-series controller.

        Args:
        Returns: bool
        """
        return all((
            self.is_rseries,
            self.model.startswith((
                ControllerModels.R50.value,
                ControllerModels.R50B.value,
                ControllerModels.R50BM.value,
            ))
        ))

    @property
    def is_r60(self):
        """Determine if the enclosure device is an r60 controller.

        Args:
        Returns: bool
        """
        return all((
            self.is_rseries,
            (self.model == ControllerModels.R60.value),
        ))

    @property
    def is_fseries(self):
        """Determine if the enclosure device is a f-series controller.

        Args:
        Returns: bool
        """
        return all((self.controller, self.model and self.model[0] == 'F'))

    @property
    def is_hseries(self):
        """Determine if the enclosure device is a h-series controller.

        Args:
        Returns: bool
        """
        return all((self.controller, self.model and self.model[0] == 'H'))

    @property
    def is_mseries(self):
        """Determine if the enclosure device is a m-series controller.

        Args:
        Returns: bool
        """
        return all((
            self.controller, not self.is_mini, self.model and self.model[0] == 'M'
        ))

    @property
    def is_vseries(self):
        return self.controller and self.model and self.model[0] == 'V'

    @property
    def is_xseries(self):
        """Determine if the enclosure device is a x-series controller.

        Args:
        Returns: bool
        """
        return all((
            self.controller, self.model and self.model[0] == 'X'
        ))

    @property
    def is_mini(self):
        """Determine if the enclosure device is a mini-series controller.

        Args:
        Returns: bool
        """
        return all((
            self.controller, self.model.startswith(MINI_MODEL_BASE)
        ))

    @property
    def is_mini_3e(self):
        """Determine if the enclosure device is a MINI-3.0-E.

        Args:
        Returns: bool
        """
        return all((
            self.is_mini,
            self.model == ControllerModels.MINI3E.value
        ))

    @property
    def is_mini_3e_plus(self):
        """Determine if the enclosure device is a MINI-3.0-E+.

        Args:
        Returns: bool
        """
        return all((
            self.is_mini,
            self.model == ControllerModels.MINI3EP.value
        ))

    @property
    def is_mini_3_x(self):
        """Determine if the enclosure device is a MINI-3.0-X.

        Args:
        Returns: bool
        """
        return all((
            self.is_mini,
            self.model == ControllerModels.MINI3X.value
        ))

    @property
    def is_mini_3_x_plus(self):
        """Determine if the enclosure device is a MINI-3.0-X+.

        Args:
        Returns: bool
        """
        return all((
            self.is_mini,
            self.model == ControllerModels.MINI3XP.value
        ))

    @property
    def is_mini_3_xl_plus(self):
        """Determine if the enclosure device is a MINI-3.0-XL+.

        Args:
        Returns: bool
        """
        return all((
            self.is_mini,
            self.model == ControllerModels.MINI3XLP.value
        ))

    @property
    def is_mini_r(self):
        """Determine if the enclosure device is a mini-r-series controller.

        Args:
        Returns: bool
        """
        return all((self.is_mini, self.model.startswith(MINIR_MODEL_BASE)))

    @property
    def is_12_bay_jbod(self):
        """Determine if the enclosure device is a 12 bay JBOD.

        Args:
        Returns: bool
        """
        return all((
            self.is_jbod,
            (self.model == JbodModels.ES12.value),
        ))

    @property
    def is_24_bay_jbod(self):
        """Determine if the enclosure device is a 24 bay JBOD.

        Args:
        Returns: bool
        """
        return all((
            self.is_jbod,
            self.model in (
                JbodModels.ES24.value,
                JbodModels.ES24F.value,
            )
        ))

    @property
    def is_60_bay_jbod(self):
        """Determine if the enclosure device is a 60 bay JBOD.

        Args:
        Returns: bool
        """
        return all((
            self.is_jbod,
            self.model in (
                JbodModels.ES60.value,
                JbodModels.ES60G2.value,
                JbodModels.ES60G3.value,
            )
        ))

    @property
    def is_102_bay_jbod(self):
        """Determine if the enclosure device is a 102 bay JBOD.

        Args:
        Returns: bool
        """
        return all((
            self.is_jbod,
            self.model in (
                JbodModels.ES102.value,
                JbodModels.ES102G2.value,
            )
        ))

    @property
    def rackmount(self):
        """Determine if the enclosure device is a rack mountable unit.

        Args:
        Returns: bool
        """
        return any((
            self.is_jbod,
            self.is_mini_r,
            self.is_rseries,
            self.is_fseries,
            self.is_hseries,
            self.is_mseries,
            self.is_vseries,
            self.is_xseries,
        ))

    @property
    def top_loaded(self):
        """Determine if the enclosure device has its disk slots loaded
        from the top.

        Args:
        Returns: bool
        """
        return any((
            self.is_r50_series,
            self.is_60_bay_jbod,
            self.is_102_bay_jbod
        ))

    @property
    def top_slots(self):
        """Determine the total number of top drive bays.

        Args:
        Returns: int
        """
        if self.top_loaded:
            if self.is_r50_series:
                return 48
            elif self.is_60_bay_jbod:
                return 60
            elif self.is_102_bay_jbod:
                return 102
            else:
                return 0
        return 0

    @property
    def front_loaded(self):
        """Determine if the enclosure device has its disk slots loaded
        from the front.

        Args:
        Returns: bool
        """
        return any((
            self.is_12_bay_jbod,
            self.is_24_bay_jbod,
            self.is_fseries,
            self.is_hseries,
            self.is_mini,
            self.is_mseries,
            self.is_vseries,
            self.is_r10,
            self.is_r20_series,
            self.is_r30,
            self.is_r40,
            self.is_r60,
            self.is_xseries,
        ))

    @property
    def front_slots(self):
        """Determine the total number of front drive bays.

        Args:
        Returns: int
        """
        if self.front_loaded:
            if any((self.is_mini_3e, self.is_mini_3e_plus)):
                return 6
            elif any((self.is_mini_3_x, self.is_mini_3_x_plus)):
                return 7
            elif self.is_mini_3_xl_plus:
                return 10
            elif any((
                self.is_mini_r,
                self.is_hseries,
                self.is_xseries,
                self.is_r20_series,
                self.is_r30,
                self.is_r60,
                self.is_12_bay_jbod,
            )):
                return 12
            elif self.is_r10:
                return 16
            elif any((self.is_fseries, self.is_mseries, self.is_vseries, self.is_24_bay_jbod)):
                return 24
            elif self.is_rseries:
                return 48
            else:
                return 0
        return 0

    @property
    def rear_slots(self):
        """Determine the total number of rear drive bays.

        Args:
        Returns: int
        """
        if not self.model:
            return 0
        elif self.is_r20_series or self.model == ControllerModels.R50B.value:
            return 2
        elif self.model == ControllerModels.R50.value:
            return 3
        elif self.model in (
            ControllerModels.M50.value,
            ControllerModels.M60.value,
            ControllerModels.V140.value,
            ControllerModels.V160.value,
            ControllerModels.V260.value,
            ControllerModels.V280.value,
            ControllerModels.R50BM.value,
        ):
            return 4
        else:
            return 0

    @property
    def internal_slots(self):
        """Determine the total number of internal drive bays.

        Args:
        Returns: int
        """
        return 4 if self.is_r30 else 0

    def determine_disk_slot_positions(self):
        """Determine the disk slot positions in the enclosure.
        Is this a front slot, rear slot or internal slot?

        NOTE: requested by UI team so that when a user clicks on
        a slot in the UI for a given enclosure, it will update the
        picture to the rear of the machine if the slot chosen is
        a rear slot (ditto for internal or front slots)

        Args:
        Returns: dict
        """
        fs, rs, ins, ts = self.front_slots, self.rear_slots, self.internal_slots, self.top_slots
        has_rear = has_internal = False
        has_front = has_top = False
        if fs:
            has_front = True
            total = fs
        elif ts:
            has_top = True
            total = ts
        else:
            # huh? shouldn't happen
            return dict()

        if rs:
            has_rear = True
            total += rs
        elif ins:
            # NOTE: only 1 platform has internal slots
            # and it DOES NOT have rear slots. If we
            # ever have a platform that has both rear
            # AND internal slots, this logic wont work
            # and we'll need to fix it
            has_internal = True
            total += ins

        rv = dict()
        for slot in range(1, total + 1):
            rv[slot] = {
                DISK_FRONT_KEY: True if has_front and slot <= fs else False,
                DISK_TOP_KEY: True if has_top and slot <= ts else False,
                DISK_REAR_KEY: True if has_rear and slot > (fs or ts) else False,
                DISK_INTERNAL_KEY: True if has_internal and slot > (fs or ts) else False,
            }

        return rv
