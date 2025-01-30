from collections.abc import Generator

from pyudev import Context

from .private_utils import DiskEntry, __get_disks_impl, __get_serial_lunid

__all__ = ("get_disks",)


def get_disks() -> Generator[DiskEntry]:
    """Iterate over /dev and yield a `DiskEntry` object for
    each disk detected on the system."""
    ctx = Context()
    for name, devpath in __get_disks_impl():
        serial, lunid = __get_serial_lunid(ctx, name)
        yield DiskEntry(
            name=name,
            devpath=devpath,
            serial=serial,
            lunid=lunid,
        )
