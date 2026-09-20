from __future__ import annotations

import os
from typing import Any

from truenas_os_pyutils.mount import StatmountResultDict, iter_mountinfo

from middlewared.service import CallError, ServiceContext

from .utils import has_internal_path
from .zvol_utils import zvol_name_to_path

__all__ = ("processes_using_dataset_tree",)

MOUNTINFO_ATTEMPTS = 5


def read_mountinfo(name: str) -> list[StatmountResultDict]:
    """Read the whole mount table, ZFS snapshot automounts included.

    `iter_mountinfo` resolves each id it gets from `listmount(2)` with its own
    `statmount(2)`, so a mount unmounted in between raises `FileNotFoundError` and
    ends the generator with the rest of the table unread. That is ordinary churn (ZFS
    snapshot automounts alone expire on a timer), and a partial table is unusable
    here: an entry missing from the end may be the busy dataset. So the read starts
    over, a bounded number of times.

    Args:
        name: Pool being scanned, for the error message

    Returns:
        Every mount on the system, as read in a single uninterrupted pass
    """
    for _ in range(MOUNTINFO_ATTEMPTS):
        try:
            return list(iter_mountinfo(include_snapshot_mounts=True))
        except FileNotFoundError as e:
            error = e

    raise CallError(f"{name}: mount table kept changing while it was being read to scan for open files") from error


def pool_scan_targets(name: str) -> tuple[list[int], list[str]]:
    """Device ids and paths to scan for open files under `name`.

    The devices come from mountinfo rather than from the dataset list, because what
    blocks a teardown is the mount tree, not the datasets. Only mounted filesystems
    appear there, which is what the caller needs: an unmounted dataset holds no open
    files, and its mountpoint directory, if one is even left behind, belongs to
    whichever filesystem it sits on rather than to this pool. Datasets mounted
    somewhere other than their default location are covered too.

    Taking the device id straight from mountinfo also avoids stat'ing the mountpoint,
    which resolves whatever is mounted topmost at that path. A dataset with a foreign
    filesystem mounted over it would otherwise report the overmount's device and hide
    its own holders.

    ZFS snapshot automounts under `.zfs/snapshot` are included: they are unmounted
    during a teardown like any other mount, so a process holding one open blocks an
    export just the same.

    Args:
        name: Pool or dataset whose scan targets should be collected

    Returns:
        Device ids of the mounted filesystems, and paths for anything not represented
        by a mount, excluding internal datasets and their snapshots
    """
    prefixes = (f"{name}/", f"{name}@")
    devices = []
    for mnt in read_mountinfo(name):
        source = mnt["mount_source"]
        if (
            mnt["fs_type"] == "zfs"
            and source is not None
            and (source == name or source.startswith(prefixes))
            # strip any @snapshot suffix so snapshots of internal datasets stay excluded
            and not has_internal_path(source.split("@", 1)[0])
        ):
            devices.append(mnt["device_id"]["dev_t"])

    # Zvols are block devices rather than mounts, so mountinfo knows nothing about
    # them. /dev/zvol mirrors the pool's zvol hierarchy and processes_using_paths
    # walks a /dev/zvol directory recursively, so this one path covers every zvol
    # device in the tree, snapshot devices included. Skip it when the pool has no
    # zvols at all: a path that resolves to nothing still counts as something to
    # match against, which costs a readlink on every open file descriptor scanned.
    paths = []
    if os.path.exists(zvol_path := zvol_name_to_path(name)):
        paths.append(zvol_path)

    return devices, paths


async def processes_using_dataset_tree(ctx: ServiceContext, name: str) -> list[dict[str, Any]]:
    """Find processes with open files on a dataset or on any dataset beneath it.

    Matching open files by the device id of a single mountpoint is not enough: every
    ZFS dataset is a separate filesystem with its own device id, so a process holding a
    child dataset open would be invisible. Anything acting on a whole subtree has to
    scan all of it, otherwise a busy child is missed and the pool fails to export.

    Internal datasets are left out of the mount scan. Their consumers are shut down
    separately (the attachment delegates for apps, the `pool.pre_export` hook for
    the system dataset), and treating them as ordinary datasets here would mean
    killing processes that hold the system dataset open.

    Args:
        ctx: Service context
        name: Dataset to scan along with all of its descendants

    Returns:
        Processes with open files on any of them
    """
    devices, paths = await ctx.to_thread(pool_scan_targets, name)
    return await ctx.call2(ctx.s.zfs.resource.processes_using_paths, paths, devices=devices)
