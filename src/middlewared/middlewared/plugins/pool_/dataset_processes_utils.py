from __future__ import annotations

from truenas_os_pyutils.mount import iter_mountinfo

from middlewared.plugins.zfs.utils import has_internal_path
from middlewared.plugins.zfs_.utils import zvol_name_to_path
from middlewared.service import ServiceContext

__all__ = ("processes_using_dataset_tree",)


def mounted_pool_paths(name: str) -> list[str]:
    """Mountpoints of everything mounted from `name` or a dataset beneath it.

    Read from mountinfo rather than from the dataset list, because what blocks a
    teardown is the mount tree, not the datasets. Only mounted filesystems appear
    here, which is what the caller needs: an unmounted dataset holds no open files,
    and its mountpoint directory, if one is even left behind, belongs to whichever
    filesystem it sits on rather than to this pool. Datasets mounted somewhere other
    than their default location are covered too.

    ZFS snapshot automounts under `.zfs/snapshot` are included: they are unmounted
    during a teardown like any other mount, so a process holding one open blocks an
    export just the same.

    Args:
        name: Pool or dataset whose mount tree should be collected

    Returns:
        Absolute mountpoint paths, excluding internal datasets and their snapshots
    """
    prefixes = (f"{name}/", f"{name}@")
    return [
        mnt["mountpoint"]
        for mnt in iter_mountinfo(include_snapshot_mounts=True)
        if (
            mnt["fs_type"] == "zfs"
            and mnt["mountpoint"] is not None
            and (source := mnt["mount_source"]) is not None
            and (source == name or source.startswith(prefixes))
            # strip any @snapshot suffix so snapshots of internal datasets stay excluded
            and not has_internal_path(source.split("@", 1)[0])
        )
    ]


async def processes_using_dataset_tree(ctx: ServiceContext, name: str) -> list[dict]:
    """Find processes with open files on a dataset or on any dataset beneath it.

    `pool.dataset.processes` only covers the single dataset it is given. It matches
    open files by the device id of the scanned mountpoint, and every ZFS dataset is a
    separate filesystem with its own device id, so a process holding a child dataset
    open is invisible to it. Anything acting on a whole pool has to scan the entire
    tree, otherwise a busy child is missed and the pool fails to export.

    Internal datasets are left out of the mount scan. Their consumers are shut down
    separately (the attachment delegates for apps, the `pool.pre_export` hook for
    the system dataset), and treating them as ordinary datasets here would mean
    killing processes that hold the system dataset open.

    Args:
        ctx: Service context
        name: Dataset to scan along with all of its descendants

    Returns:
        Processes as reported by `pool.dataset.processes_using_paths`
    """
    paths = await ctx.to_thread(mounted_pool_paths, name)

    # Zvols are block devices rather than mounts, so mountinfo knows nothing about
    # them. /dev/zvol mirrors the pool's zvol hierarchy and processes_using_paths
    # walks a /dev/zvol directory recursively, so this one path covers every zvol
    # device in the tree, snapshot devices included. A zvol with no device node
    # yet is never matched, but it cannot be held open either.
    paths.append(zvol_name_to_path(name))

    return await ctx.middleware.call("pool.dataset.processes_using_paths", paths)
