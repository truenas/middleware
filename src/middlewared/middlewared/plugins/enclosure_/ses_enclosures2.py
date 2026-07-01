from contextlib import suppress
from logging import getLogger
from pathlib import Path
from typing import Iterable

from libsg3.ses import EnclosureDevice
from .constants import (
    ARRAY_DEVICE_SLOT_ELEMENT_TYPE,
    SLOT_DESCRIPTOR_RE,
    VSERIES_FRONT_PRODUCTS,
    VSERIES_REAR_PRODUCTS,
)
from .enclosure_class import ElementsDict, Enclosure, EnclosureStatusDict

logger = getLogger(__name__)


def get_ses_enclosure_status(bsg_path: str) -> EnclosureStatusDict | None:
    try:
        return EnclosureDevice(bsg_path).status()
    except OSError:
        logger.error('Error querying enclosure status for %r', bsg_path, exc_info=True)


def _extend_rv(rv: list, iterable: Iterable[Enclosure], asdict: bool = True) -> None:
    """Extend `rv` with `iterable`. Convert Enclosures to dictionaries if `asdict`."""
    if asdict:
        rv.extend(enc.asdict() for enc in iterable)
    else:
        rv.extend(iterable)


def _vseries_slot_designation_from_descriptors(elements: ElementsDict) -> str | None:
    """Derive a V-series slot_designation by inspecting Array Device Slot
    element descriptors. V-series VirtualSES enclosures label the slots each
    partition owns as 'slot01'..'slot12' (NVME0 partition) or
    'slot13'..'slot24' (NVME8 partition); slots not owned by a partition are
    reported with descriptor '<empty>'.

    Returns 'NVME0', 'NVME8', or None if the descriptors don't clearly
    identify a single partition.
    """
    has_low = False
    has_high = False
    for element in elements.values():
        if element.get('type') != ARRAY_DEVICE_SLOT_ELEMENT_TYPE:
            continue
        match = SLOT_DESCRIPTOR_RE.match(element.get('descriptor', '').strip())
        if not match:
            continue
        slot_num = int(match.group(1))
        if 1 <= slot_num <= 12:
            has_low = True
        elif 13 <= slot_num <= 24:
            has_high = True
    if has_low and not has_high:
        return 'NVME0'
    if has_high and not has_low:
        return 'NVME8'
    return None


def _initialize_v_series_front_enclosures(
    rv: list, deferred: list[tuple[Enclosure, ElementsDict]], asdict: bool = True
) -> None:
    """Assign NVME0/NVME8 to the two V-series front-bay enclosures.

    V1xx HBAs have distinct encids (compared). V2xx PEX89088 partitions
    share an encid — fall back to Array Device Slot descriptor labels
    ('slot01'..'slot12' = NVME0; 'slot13'..'slot24' = NVME8).
    """
    if len(deferred) != 2:
        logger.error('Unable to map elements: Expected 2 V-series front-bay enclosures, found %r', len(deferred))
        return _extend_rv(rv, (enc.initialize(status) for enc, status in deferred), asdict)

    (enc1, elements1), (enc2, elements2) = deferred
    hex_id1 = int(enc1.encid, 16)
    hex_id2 = int(enc2.encid, 16)

    if hex_id1 < hex_id2:
        enc1.initialize(elements1, slot_designation='NVME0')
        enc2.initialize(elements2, slot_designation='NVME8')
    elif hex_id1 > hex_id2:
        enc1.initialize(elements1, slot_designation='NVME8')
        enc2.initialize(elements2, slot_designation='NVME0')
    else:
        # V2xx: both VirtualSES enclosures share an encid because they are
        # two partitions of a single PEX89088 chip. Disambiguate by reading
        # the Array Device Slot element descriptor labels each partition
        # advertises.
        d1 = _vseries_slot_designation_from_descriptors(elements1)
        d2 = _vseries_slot_designation_from_descriptors(elements2)
        if d1 and d2 and d1 != d2:
            enc1.initialize(elements1, slot_designation=d1)
            enc2.initialize(elements2, slot_designation=d2)
        else:
            logger.error(
                'Unable to map elements: V-series front-bay enclosures share encid %r and could not be '
                'disambiguated by element descriptor labels (got %r and %r)',
                enc1.encid, d1, d2,
            )
            return _extend_rv(rv, (enc.initialize(status) for enc, status in deferred), asdict)

    _extend_rv(rv, (enc1, enc2), asdict)


def _vseries_rear_partition_owns_bays(elements: ElementsDict) -> bool:
    """True if this NTG partition serves the 4 rear bays (descriptors
    'slot01'..'slot04'); the no-drives partition reports all slots '<empty>'.
    """
    for element in elements.values():
        if element.get('type') != ARRAY_DEVICE_SLOT_ELEMENT_TYPE:
            continue
        match = SLOT_DESCRIPTOR_RE.match(element.get('descriptor', '').strip())
        if match and 1 <= int(match.group(1)) <= 4:
            return True
    return False


def _initialize_v_series_rear_enclosures(
    rv: list, deferred: list[tuple[Enclosure, ElementsDict]], asdict: bool = True
) -> None:
    """Keep the bay-serving half of the bifurcated NTG chip as 'REAR';
    drop the no-drives half so it doesn't surface in enclosure2.query.
    """
    if len(deferred) != 2:
        logger.error('Unable to map elements: Expected 2 V-series rear-bay enclosures, found %r', len(deferred))
        return _extend_rv(rv, (enc.initialize(status) for enc, status in deferred), asdict)

    bay_partitions = [(enc, els) for enc, els in deferred if _vseries_rear_partition_owns_bays(els)]
    if len(bay_partitions) != 1:
        logger.error(
            'Unable to map elements: expected exactly 1 rear-bay-serving partition among %r, found %r',
            [enc.product for enc, _ in deferred], len(bay_partitions),
        )
        return _extend_rv(rv, (enc.initialize(status) for enc, status in deferred), asdict)

    enc, elements = bay_partitions[0]
    enc.initialize(elements, slot_designation='REAR')
    _extend_rv(rv, (enc,), asdict)


def get_ses_enclosures(asdict=True):
    rv = list()
    deferred_front = list()
    deferred_rear = list()

    with suppress(FileNotFoundError):
        for i in Path('/sys/class/enclosure').iterdir():
            bsg = f'/dev/bsg/{i.name}'
            if (status := get_ses_enclosure_status(bsg)):
                sg = next((i / 'device/scsi_generic').iterdir())
                enc = Enclosure(bsg, f'/dev/{sg.name}', status)

                if enc.is_vseries and (
                    status['name'] == 'BROADCOMVirtualSES0001'
                    or enc.product in VSERIES_FRONT_PRODUCTS
                ):
                    # V-series front-bay: defer for NVME0/NVME8 disambiguation.
                    deferred_front.append((enc, status['elements']))
                elif enc.is_vseries and enc.product in VSERIES_REAR_PRODUCTS:
                    # V-series rear-bay: defer to pick bay-serving partition.
                    deferred_rear.append((enc, status['elements']))
                else:
                    enc.initialize(status['elements'])
                    rv.append(enc.asdict() if asdict else enc)

    if deferred_front:
        _initialize_v_series_front_enclosures(rv, deferred_front, asdict)
    if deferred_rear:
        _initialize_v_series_rear_enclosures(rv, deferred_rear, asdict)

    return rv
