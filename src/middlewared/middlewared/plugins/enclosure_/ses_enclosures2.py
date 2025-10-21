from contextlib import suppress
from logging import getLogger
from pathlib import Path
from typing import Iterable

from libsg3.ses import EnclosureDevice
from .enclosure_class import ElementsDict, Enclosure

logger = getLogger(__name__)


def get_ses_enclosure_status(bsg_path):
    try:
        return EnclosureDevice(bsg_path).status()
    except OSError:
        logger.error('Error querying enclosure status for %r', bsg_path, exc_info=True)


def _initialize_v_series_enclosures(
    rv: list, deferred_enclosures: list[tuple[Enclosure, ElementsDict]], asdict: bool = True
) -> None:
    """
    Compare the encids (SAS addresses) of the two VirtualSES enclosures
    to determine their slot designations for initialization.
    """
    def extend_rv(iter: Iterable[Enclosure]):
        if asdict:
            rv.extend(enc.asdict() for enc in iter)
        else:
            rv.extend(iter)

    if len(deferred_enclosures) != 2:
        logger.error('Unable to map elements: Expected 2 VirtualSES enclosures, found %r', len(deferred_enclosures))
        return extend_rv(enc.initialize(status) for enc, status in deferred_enclosures)

    (enc1, elements1), (enc2, elements2) = deferred_enclosures
    hex_id1 = int(enc1.encid, 16)
    hex_id2 = int(enc2.encid, 16)

    if hex_id1 < hex_id2:
        enc1.initialize(elements1, slot_designation='NVME0')
        enc2.initialize(elements2, slot_designation='NVME8')
    elif hex_id1 > hex_id2:
        enc1.initialize(elements1, slot_designation='NVME8')
        enc2.initialize(elements2, slot_designation='NVME0')
    else:
        logger.error('Unable to map elements: Both VirtualSES enclosures have the same ID / SAS address')
        return extend_rv(enc.initialize(status) for enc, status in deferred_enclosures)

    extend_rv((enc1, enc2))


def get_ses_enclosures(asdict=True):
    rv = list()
    deferred_enclosures = list()

    with suppress(FileNotFoundError):
        for i in Path('/sys/class/enclosure').iterdir():
            bsg = f'/dev/bsg/{i.name}'
            if (status := get_ses_enclosure_status(bsg)):
                sg = next((i / 'device/scsi_generic').iterdir())
                enc = Enclosure(bsg, f'/dev/{sg.name}', status['id'], status['status'])

                if enc.is_vseries and status['name'] == 'BROADCOMVirtualSES0001':
                    # Carve-out for V-series since their slot mappings depend on the
                    # SAS address of the opposite VirtualSES enclosure
                    deferred_enclosures.append((enc, status['elements']))
                else:
                    # Every other system can initialize their enclosures independently
                    enc.initialize(status['elements'])
                    rv.append(enc.asdict() if asdict else enc)

    if deferred_enclosures:
        _initialize_v_series_enclosures(rv, deferred_enclosures, asdict)

    return rv
