# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file COPYING.IX for complete terms and conditions

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BaseDev:
    name: str = None


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
    for i in Path(f'/sys/class/enclosure/{pci}').iterdir():
        try:
            slot = int((i / 'slot').read_text().strip())
        except (NotADirectoryError, FileNotFoundError, ValueError):
            # not a slot directory
            continue
        else:
            try:
                mapping[slot] = next((i / 'device/block').iterdir(), BaseDev).name
            except FileNotFoundError:
                # no disk in this slot
                mapping[slot] = BaseDev.name

    return mapping
