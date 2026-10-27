from __future__ import annotations

from collections.abc import Iterable

from truenas_pylibzfs import ZFSError, ZFSException, libzfs_types

from .exceptions import (
    ZpoolNotFoundException,
    ZpoolVdevIsCacheException,
    ZpoolVdevIsSpareException,
    ZpoolVdevNotDiskException,
    ZpoolVdevNotFoundException,
)

__all__ = ("find_disk_vdev", "offline_impl", "online_impl")


def _find_vdev(vdevs: Iterable[libzfs_types.struct_vdev], guid: str) -> libzfs_types.struct_vdev | None:
    for vdev in vdevs:
        if str(vdev.guid) == guid:
            return vdev
        if vdev.children and (found := _find_vdev(vdev.children, guid)) is not None:
            return found
    return None


def find_disk_vdev(zpool: libzfs_types.ZFSPool, guid: str, *, allow_cache: bool = True) -> libzfs_types.struct_vdev:
    """Return the disk vdev of `zpool` whose GUID is `guid` (decimal).

    Only disks are accepted. Offlining an interior vdev (mirror, raidz, spare)
    or a dRAID distributed spare fails in the kernel with ENOTSUP, which libzfs
    words as "operation not supported on this type of pool", and onlining one
    is not refused by the kernel at all. A hot spare that is not in use is
    refused, as libzfs would refuse it; one in use is found in the vdev it
    replaces and is allowed. With `allow_cache` false a cache device is
    refused too: libzfs will not bring a cache device back online while the
    pool's autoexpand property is on, as it is on every pool TrueNAS creates.
    """
    status = zpool.status(get_stats=False)
    vdevs = list(status.storage_vdevs)
    for vtype in ("cache", "log", "special", "dedup"):
        vdevs.extend(getattr(status.support_vdevs, vtype))

    vdev = _find_vdev(vdevs, guid)
    if vdev is None:
        if _find_vdev(status.spares, guid) is not None:
            raise ZpoolVdevIsSpareException(zpool.name, guid)
        raise ZpoolVdevNotFoundException(zpool.name, guid)
    if vdev.vdev_type != "disk":
        raise ZpoolVdevNotDiskException(zpool.name, guid, vdev.vdev_type)
    if not allow_cache and any(cache.guid == vdev.guid for cache in status.support_vdevs.cache):
        raise ZpoolVdevIsCacheException(zpool.name, guid)
    return vdev


def _open_pool(lzh: libzfs_types.ZFS, pool_name: str) -> libzfs_types.ZFSPool:
    try:
        return lzh.open_pool(name=pool_name)
    except ZFSException as e:
        if e.code == ZFSError.EZFS_NOENT:
            raise ZpoolNotFoundException(pool_name) from e
        raise


def offline_impl(lzh: libzfs_types.ZFS, pool_name: str, guid: str) -> None:
    zpool = _open_pool(lzh, pool_name)
    vdev = find_disk_vdev(zpool, guid, allow_cache=False)
    zpool.offline_device(device=str(vdev.guid))


def online_impl(lzh: libzfs_types.ZFS, pool_name: str, guid: str) -> None:
    zpool = _open_pool(lzh, pool_name)
    vdev = find_disk_vdev(zpool, guid)
    zpool.online_device(device=str(vdev.guid))
