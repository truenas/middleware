import pathlib
import typing

import truenas_pylibzfs

__all__ = ("get_zpool_disks_impl",)


def _get_whole_disk(disk: str) -> str:
    """Resolve a device path to its whole-disk device name.

    Strips the '/dev/' prefix and, for partition devices (e.g.
    /dev/sda1, /dev/nvme0n1p1), returns the parent whole-disk
    device name (e.g. sda, nvme0n1) by reading the sysfs
    'partition' marker. Devices that are already whole disks
    are returned as-is.

    Args:
        disk: Absolute device path (e.g. '/dev/sda1', '/dev/nvme0n1p1').

    Returns:
        The whole-disk device name without '/dev/' prefix (e.g. 'sda', 'nvme0n1').
    """
    dev_name = disk.removeprefix("/dev/")
    sys_path = pathlib.Path(f"/sys/class/block/{dev_name}")
    if (sys_path / "partition").exists():
        # readlink returns the raw symlink target (e.g.
        # ../../devices/.../block/sda/sda1) without walking
        # every component like resolve() does. The parent of
        # that relative path is the whole-disk device name.
        return sys_path.readlink().parent.name
    return dev_name


def get_zpool_disks_impl(lzh: typing.Any, pool_name: str | None) -> list[str]:
    """Return all whole-disk device names belonging to a zpool.

    Collects disks from storage vdevs, support vdevs (cache, log,
    special, dedup), and spares. Pools in a non-recoverable state
    are skipped, returning an empty list.

    Args:
        lzh: libzfs handle providing ``open_pool()``.
        pool_name: Name of the zpool to inspect.

    Returns:
        A list of whole-disk device names (e.g. ['sda', 'sdb']).
    """
    disks: list[str] = list()
    status = lzh.open_pool(name=pool_name).status(get_stats=False)
    if status.status in truenas_pylibzfs.property_sets.ZPOOL_STATUS_NONRECOVERABLE:
        return disks

    for i in status.storage_vdevs:
        for j in filter(lambda x: x.vdev_type == "disk", i.children):
            # skip non-disk vdevs
            disks.append(_get_whole_disk(j.name))

    for vtype in ("cache", "log", "special", "dedup"):
        for j in getattr(status.support_vdevs, vtype):
            disks.append(_get_whole_disk(j.name))

    for i in status.spares:
        disks.append(_get_whole_disk(i.name))

    return disks
