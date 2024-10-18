# Copyright (c) - iXsystems Inc.
#
# Licensed under the terms of the TrueNAS Enterprise License Agreement
# See the file LICENSE.IX for complete terms and conditions

from dataclasses import dataclass
from os import scandir
from pathlib import Path

from .enums import ControllerModels


@dataclass(slots=True, frozen=True, kw_only=True)
class BaseDev:
    name: str | None = None
    locate: str | None = None


def map_disks_to_enclosure_slots(enc) -> dict[int, BaseDev]:
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
        enc: An instance of class Enclosure

    """
    mapping = dict()
    with scandir(f"/sys/class/enclosure/{enc.pci}") as sdir:
        for i in filter(lambda x: x.is_dir(), sdir):
            if enc.is_hseries and i.name in ("4", "5", "6", "7"):
                continue

            path = Path(i)
            try:
                slot = int((path / "slot").read_text().strip())
            except (NotADirectoryError, FileNotFoundError, ValueError):
                # not a slot directory
                continue
            else:
                try:
                    name = next((path / "device/block").iterdir(), None).name
                except (AttributeError, FileNotFoundError):
                    # no disk in this slot
                    name = None
                try:
                    locate = (
                        "ON" if (path / "locate").read_text().strip() == "1" else "OFF"
                    )
                except (ValueError, FileNotFoundError):
                    locate = None

                mapping[slot] = BaseDev(name=name, locate=locate)

    return mapping


def toggle_enclosure_slot_identifier(
    sysfs_path, slot, action, by_dirname=False, model=None
):
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
        raise FileNotFoundError(f"Enclosure path: {sysfs_path!r} not found")

    slot_errmsg = f"Slot: {slot!r} not found"
    slot = str(slot)
    if model in (ControllerModels.H10.value, ControllerModels.H20.value):
        # kernel bug for hseries where the slot files report duplicate numbers
        # between the array device slots so until that can be fixed, we have to
        # use the directory name where the slot file exists. Only applies to 4
        # slots on the HBA
        match slot:
            case "4":
                slot = "12"
                by_dirname = True
            case "5":
                slot = "13"
                by_dirname = True
            case "6":
                slot = "14"
                by_dirname = True
            case "7":
                slot = "15"
                by_dirname = True

    if by_dirname:
        pathobj = Path(f"{sysfs_path}/{slot}")
        if not pathobj.exists():
            raise FileNotFoundError(slot_errmsg)
    else:
        for i in pathobj.iterdir():
            slot_path = i / "slot"
            if slot_path.exists() and slot_path.read_text().strip() == slot:
                pathobj = i
                break
        else:
            raise FileNotFoundError(slot_errmsg)

    match action:
        case "CLEAR" | "OFF":
            value = "0"
        case "ON":
            value = "1"
        case _:
            raise ValueError(f"Invalid action ({action!r})")

    (pathobj / "locate").write_text(value)
