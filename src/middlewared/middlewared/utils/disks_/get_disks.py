from collections.abc import Generator

from pyudev import Context

from .gpt_parts import __get_gpt_parts_impl
from .private_utils import DiskEntry, __get_disks_impl, __get_serial_lunid

__all__ = ("get_disks",)


def get_disks(
    get_partitions: bool = False, name_filters: list[str] | None = None
) -> Generator[DiskEntry]:
    """Iterate over /dev and yield a `DiskEntry` object for
    each disk detected on the system.

    Args:
        get_partitions: bool if True, will enumerate
            GPT partition information
        name_filters: list of strings, represent a list
            of disk names that will be filtered upon.
            The name of the disk may take the form
            of 'sda' or '/dev/sda'.
    """
    ctx = Context()
    for name, devpath in __get_disks_impl():
        if name_filters is None or name in name_filters or devpath in name_filters:
            serial, lunid = __get_serial_lunid(ctx, name)
            parts = None
            if get_partitions:
                try:
                    parts = __get_gpt_parts_impl(devpath)
                except Exception:
                    # On an internal system, a disk died in
                    # a spectacular way. Issuing an ioctl and
                    # stat'ing the disk returned just fine.
                    # However, the moment I/O was issued, it
                    # fell over. No reason to fail on a single
                    # disk.
                    pass

            yield DiskEntry(
                name=name,
                devpath=devpath,
                serial=serial,
                lunid=lunid,
                parts=parts,
            )
