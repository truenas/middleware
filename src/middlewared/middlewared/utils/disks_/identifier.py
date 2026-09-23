from __future__ import annotations

import collections.abc
import re

__all__ = ("build_identifier", "join_serial_lunid", "sanitize_serial")

# Control characters and DEL are invalid in a serial per SPC-4. The double
# quote and backslash are valid but never used in real ones, and both break
# netdata, which embeds serials in chart names without escaping (NAS-139489).
RE_SERIAL_STRIP = re.compile(r"[\x00-\x1f\x7f\x22\x5c]")


def sanitize_serial(serial: str) -> str | None:
    return RE_SERIAL_STRIP.sub("", serial).strip() or None


def join_serial_lunid(serial: str | None, lunid: str | None) -> str | None:
    return f"{serial}_{lunid}" if serial and lunid else None


def build_identifier(
    name: str,
    serial_lunid: str | None,
    serial: str | None,
    zfs_partition_uuid: collections.abc.Callable[[], str | None],
) -> str:
    """Build a disk's identifier, ideally a unique one.

    `zfs_partition_uuid` is only called when the disk has no serial, because
    resolving it means reading the disk's partition table.

    NOTE: If someone is using a usb 'hub', for example, then
        all bets are off the table. Those devices will often
        report duplicate serial numbers for all disks attached
        to it AND will report the same lunid. It's impossible
        for us to handle that and this is a scenario that isn't
        supported.
    """
    if serial_lunid:
        return f"{{serial_lunid}}{serial_lunid}"
    elif serial:
        return f"{{serial}}{serial}"
    elif (uuid := zfs_partition_uuid()) is not None:
        return f"{{uuid}}{uuid}"

    return f"{{devicename}}{name}"
