from __future__ import annotations

import typing

__all__ = ("lunid_from_udev", "serial_from_udev")

# udev resolves a disk's serial with a different helper depending on the
# transport (scsi_id, ata_id or usb_id, see 60-persistent-storage.rules) and
# only scsi_id sets ID_SCSI_SERIAL, so these have to be tried in order of how
# specific they are:
#   ID_SCSI_SERIAL  VPD page 0x80, the unit serial number
#   ID_SERIAL_SHORT the ata_id or usb_id serial, or a VPD page 0x83 designator
#                   when scsi_id could not read page 0x80
#   ID_SERIAL       the same value with the vendor and model prepended, or the
#                   model alone when the drive reported no serial; virtio is
#                   the one case where it is a real serial on its own
SERIAL_KEYS = ("ID_SCSI_SERIAL", "ID_SERIAL_SHORT", "ID_SERIAL")


def _clean(value: typing.Any) -> str | None:
    return value.strip() or None if value is not None else None


def serial_from_udev(properties: typing.Mapping[str, typing.Any]) -> str | None:
    """The disk's serial number as udev resolved it, or None."""
    for key in SERIAL_KEYS:
        if (serial := _clean(properties.get(key))) is not None:
            return serial

    return None


def lunid_from_udev(properties: typing.Mapping[str, typing.Any]) -> str | None:
    """The disk's lunid as udev resolved it, or None."""
    if (lunid := _clean(properties.get("ID_WWN"))) is None:
        return None

    return lunid.removeprefix("0x").removeprefix("eui.") or None
