from collections.abc import Generator

from .disk_class import DiskEntry, __iterate_disks

__all__ = ("get_disks",)


def get_disks(*, name_filters: list[str] | None = None) -> Generator[DiskEntry]:
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
    for disk in __iterate_disks():
        if (
            name_filters is None
            or disk.name in name_filters
            or disk.devpath in name_filters
        ):
            yield disk
