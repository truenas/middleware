from __future__ import annotations

import contextlib
import typing

import pyudev

__all__ = ("lunid_from_wwn", "serial_from_udev", "udev_fallback_identity")

# udev resolves a disk's serial with a different helper depending on the
# transport (scsi_id, ata_id or usb_id, see 60-persistent-storage.rules) and
# only scsi_id sets ID_SCSI_SERIAL, so these have to be tried in order of how
# specific they are:
#   ID_SCSI_SERIAL  VPD page 0x80, the unit serial number, from scsi_id
#   ID_SERIAL_SHORT the ata_id or usb_id serial. From scsi_id it is the VPD
#                   page 0x83 designator, which scsi_id prefers over page 0x80
#                   whenever the device has one, so on SAS it is the NAA name
#   ID_SERIAL       the same value with the vendor and model prepended, or the
#                   model alone when the drive reported no serial; virtio is
#                   the one case where it is a real serial on its own
SERIAL_KEYS = ("ID_SCSI_SERIAL", "ID_SERIAL_SHORT", "ID_SERIAL")
# ID_SERIAL is left out of the sysfs fallback on purpose: when the drive has no
# serial it is the bare model, the same for every drive of that model. virtio,
# where it is a real serial, always has one in sysfs too, so it never gets here.
FALLBACK_KEYS = SERIAL_KEYS[:2]


def _clean(value: typing.Any) -> str | None:
    return value.strip() or None if value is not None else None


def _get(properties: typing.Mapping[str, typing.Any], key: str) -> str | None:
    # pyudev decodes every value as strict UTF-8 and scsi_id copies VPD page
    # 0x80 into ID_SCSI_SERIAL byte for byte, so a serial holding a byte that
    # is not UTF-8 raises here. Skip the key, not the disk.
    with contextlib.suppress(UnicodeDecodeError):
        return _clean(properties.get(key))

    return None


def serial_from_udev(properties: typing.Mapping[str, typing.Any]) -> str | None:
    """The disk's serial number as udev resolved it, or None."""
    for key in SERIAL_KEYS:
        if (serial := _clean(properties.get(key))) is not None:
            return serial

    return None


def lunid_from_wwn(wwn: typing.Any) -> str | None:
    """udev's ID_WWN as middleware's lunid: without the 0x or eui. prefix."""
    if (lunid := _clean(wwn)) is None:
        return None

    return lunid.removeprefix("0x").removeprefix("eui.") or None


def udev_fallback_identity(name: str) -> tuple[str | None, str | None]:
    """The serial and lunid udev recorded for block device `name`, for a disk
    that sysfs reports no serial for. Either is None when udev has none, and
    both are when it has no record of the device."""
    try:
        properties = pyudev.Devices.from_name(pyudev.Context(), "block", name).properties
    except Exception:
        return None, None

    # A serial usb_id recorded is the USB bridge's, shared by every LUN behind
    # it, and only ID_INSTANCE (target:lun) tells those apart. The disk table
    # has always identified a single-disk enclosure by its bridge, so its first
    # LUN keeps that; a further LUN, a card reader's second slot, must not
    # inherit it or the slots collapse into one disk.
    if (instance := _get(properties, "ID_INSTANCE")) and instance != "0:0":
        return None, None

    serial = None
    for key in FALLBACK_KEYS:
        if serial := _get(properties, key):
            break

    return serial, lunid_from_wwn(_get(properties, "ID_WWN"))
