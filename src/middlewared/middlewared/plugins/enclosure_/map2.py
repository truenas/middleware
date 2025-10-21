# Copyright (c) - iXsystems Inc. dba TrueNAS
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

import logging
import os

from .constants import HEAD_UNIT_DISK_SLOT_START_NUMBER
from .enums import ControllerModels, JbofModels

logger = logging.getLogger(__name__)


def to_ignore(enclosure):
    if not enclosure['controller']:
        # this is a JBOD and doesn't need to
        # be "combined" into any other object
        return True
    elif enclosure['model'].startswith((
        ControllerModels.F60.value,
        ControllerModels.F100.value,
        ControllerModels.F130.value,
        ControllerModels.R30.value,
        ControllerModels.R60.value,
    )):
        # these are all nvme flash systems and
        # are treated as-is
        return True
    elif enclosure['model'] in (i.name for i in JbofModels):
        # these are all nvme flash enclosures and
        # are treated as-is
        return True
    else:
        return False


def combine_enclosures(enclosures):
    """Purpose of this function is to combine certain enclosures
    Array Device Slot elements into 1. For example, the MINIs/R20s
    have their disk drives spread across multiple enclosures. We
    need to map them all into 1 unit. Another example is that we
    have platforms (M50/60, R50B) that have rear nvme drive bays.
    NVMe doesn't get exposed via a traditional SES device because,
    well, it's nvme. So we create a "fake" nvme "enclosure" that
    mimics the drive slot information that a traditional enclosure
    would do. We take these enclosure devices and simply add them
    to the head-unit enclosure object.

    NOTE: The array device slots have already been mapped to their
    human-readable slot numbers. That logic is in the `Enclosure`
    class in "enclosure_/enclosure_class.py"
    """
    head_unit_idx, to_combine, to_remove = None, dict(), list()
    r40_sas_ids = list()
    for idx, enclosure in enumerate(enclosures):
        if to_ignore(enclosure):
            continue
        elif enclosure['model'] == ControllerModels.R40.value:
            r40_sas_ids.append((int(f'0x{enclosure["id"]}', 16), idx, enclosure['pci']))
            if len(r40_sas_ids) == 2:
                # We need to check if the R40 is wired using the "legacy" method.
                # (i.e. 2x expanders 1x HBA) or the current MPI method
                # (i.e. 2x expanders 2x HBAs).
                try:
                    bus_addr1 = os.path.realpath(
                        f'/sys/class/enclosure/{r40_sas_ids[0][2]}'
                    ).split('/')[5].strip()
                    bus_addr2 = os.path.realpath(
                        f'/sys/class/enclosure/{r40_sas_ids[1][2]}'
                    ).split('/')[5].strip()
                except Exception:
                    # dont crash, just fall back to legacy
                    bus_addr1 = bus_addr2 = 1

                if bus_addr1 != bus_addr2:  # current MPI wiring
                    if bus_addr1 == '0000:19:00.0' and bus_addr2 == '0000:68:00.0':
                        # platform team confirms that the expander whose bus address of 0000:19:00.0
                        # is mapped to drives 1-24, and bus address of 0000:68:00.0 is 25-48
                        head_unit_idx = r40_sas_ids[0][1]
                        _update_idx = r40_sas_ids[1][1]
                    else:
                        head_unit_idx = r40_sas_ids[1][1]
                        _update_idx = r40_sas_ids[0][1]
                else:  # legacy wiring
                    # we've got no choice but to do this hack. The R40 has 2x HBAs
                    # in the head. One of those HBAs is disks 1-24, the other for 25-48.
                    # Unfortunately, however, this platform was shipped with both of
                    # those expanders flashed with the same firmware so there is no way
                    # to uniquely identify which expander gets mapped to 1-24 and the
                    # other to get mapped for 25-48. (Like we do with the R50)
                    #
                    # Instead, we take the sas address of the ses devices and check which
                    # enclosure device has the smaller value. The one with the smaller
                    # gets mapped as the "head-unit" (1-24) while the larger one gets
                    # mapped to drive slots 25-48.
                    if r40_sas_ids[0][0] < r40_sas_ids[1][0]:
                        head_unit_idx = r40_sas_ids[0][1]
                        _update_idx = r40_sas_ids[1][1]
                    else:
                        head_unit_idx = r40_sas_ids[1][1]
                        _update_idx = r40_sas_ids[0][1]

                # we know which enclosure has the larger sas address so we'll update
                # the array device slots so that they're 25-48.
                for origslot, newslot in zip(range(1, 25), range(25, 49)):
                    orig_info = enclosures[_update_idx]['elements']['Array Device Slot'].pop(origslot)
                    enclosures[_update_idx]['elements']['Array Device Slot'][newslot] = orig_info

                to_combine.update(enclosures[_update_idx]['elements'].pop('Array Device Slot'))
                to_remove.append(_update_idx)
        elif enclosure['elements']['Array Device Slot'].get(HEAD_UNIT_DISK_SLOT_START_NUMBER):
            # the enclosure object whose disk slot has number 1
            # will always be the head-unit
            head_unit_idx = idx
        else:
            to_combine.update(enclosure['elements'].pop('Array Device Slot', dict()))
            to_remove.append(idx)

    if head_unit_idx is not None:
        enclosures[head_unit_idx]['elements']['Array Device Slot'].update(to_combine)
        enclosures[head_unit_idx]['elements']['Array Device Slot'] = {
            k: v for k, v in sorted(enclosures[head_unit_idx]['elements']['Array Device Slot'].items())
        }
        for idx in reversed(to_remove):
            # we've combined the enclosures into the
            # main "head-unit" enclosure object so let's
            # remove the objects we combined from
            enclosures.pop(idx)
