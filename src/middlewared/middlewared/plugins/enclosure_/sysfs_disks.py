# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from os import scandir
from pathlib import Path


@dataclass(slots=True, frozen=True)
class BaseDev:
    name: str = None
    locate: str = None


def map_disks_to_enclosure_slots(pci):
    """The sysfs directory structure is dynamic based on the enclosure
    that is attached.

    Here are some examples of what we've seen on internal hardware:
        /sys/class/enclosure/19:0:6:0/SLOT_001/
        /sys/class/enclosure/13:0:0:0/Drive Slot #0_0000000000000000/
        /sys/class/enclosure/13:0:0:0/Disk #00/
        /sys/class/enclosure/13:0:0:0/Slot 00/
        /sys/class/enclosure/13:0:0:0/slot00/
        /sys/class/enclosure/13:0:0:0/slot00       / (yes those are spaces)
        /sys/class/enclosure/0:0:0:0/0/

    The safe assumption that we can make on whether or not the directory
    represents a drive slot is looking for the file named "slot" underneath
    each directory. (i.e. /sys/class/enclosure/13:0:0:0/Disk #00/slot)
    If this file doesn't exist, then it means the directory is not a disk
    slot and we move on. Once we've determined that there is a file named
    "slot", we can read the contents of that file to get the slot number
    associated to the disk device. The "slot" file is always an integer
    so we don't need to convert to hexadecimal

    Args:
        pci: string (i.e. 0:0:0:0)

    Returns:
        dictionary whose key is an integer (disk slot) and value is a device name (i.e. sda)
        If no device is found at the given slot, None is set as the value
        (i.e. {1: sda, 2: None})
    """
    mapping = dict()
    with scandir(f'/sys/class/enclosure/{pci}') as sdir:
        for i in filter(lambda x: x.is_dir(), sdir):
            path = Path(i)
            try:
                slot = int((path / 'slot').read_text().strip())
            except (NotADirectoryError, FileNotFoundError, ValueError):
                # not a slot directory
                continue
            else:
                try:
                    mapping[slot] = {
                        'name': next((path / 'device/block').iterdir(), BaseDev).name,
                        'locate': 'ON' if (path / 'locate').read_text().strip() == '1' else 'OFF',
                    }
                except (ValueError, FileNotFoundError):
                    # no disk in this slot
                    mapping[slot] = {
                        'name': BaseDev.name,
                        'locate': BaseDev.locate,
                    }

    return mapping


def toggle_enclosure_slot_identifier(sysfs_path, slot, action, by_dirname=False):
    """Use sysfs to toggle the enclosure light indicator for a disk
    slot.

    Args:
        sysfs_path: string (i.e. /sys/clas/enclosure/0:0:0:0)
        slot: string | int
        action: string
        by_dirname: bool defaults to False, when set to True will treat the
            parent directory _NAME_ as the drive "slot". For example,
            /sys/class/enclosure/0:0:0:0/1 will be treated as slot "1".
            Otherwise, the slot _FILE_ inside the parent directory will be
            read and treated as the slot. For example,
            cat /sys/class/enclosure/0:0:0:0/1/slot == 9. "9" is treated
            as the slot.

    Returns:
        None
    """
    pathobj = Path(sysfs_path)
    if not pathobj.exists():
        raise FileNotFoundError(f'Enclosure path: {sysfs_path!r} not found')

    slot_errmsg = f'Slot: {slot!r} not found'
    if by_dirname:
        pathobj = Path(f'{sysfs_path}/{slot}')
        if not pathobj.exists():
            raise FileNotFoundError(slot_errmsg)
    else:
        for i in pathobj.iterdir():
            slot_path = (i / 'slot')
            if slot_path.exists() and slot_path.read_text().strip() == str(slot):
                pathobj = i
                break
        else:
            raise FileNotFoundError(slot_errmsg)

    fault = (pathobj / 'fault')
    locate = (pathobj / 'locate')
    match action:
        case 'CLEAR':
            actions = ((fault, '0'), (locate, '0'),)
        case 'FAULT':
            actions = ((fault, '1'),)
        case 'IDENTIFY':
            actions = ((locate, '1'),)
        case _:
            raise ValueError(f'Invalid action ({action!r})')

    for path, action in actions:
        path.write_text(action)
