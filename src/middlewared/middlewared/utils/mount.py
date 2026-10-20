# NOTE: iter_mountinfo, statmount, umount, and related types were previously defined
# here and have been moved to truenas_os_pyutils:
# https://github.com/truenas/truenas_pyos/tree/master/src/truenas_os_pyutils
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import truenas_os

from middlewared.api.current import ZFSResourceQuery
from middlewared.plugins.zfs.name_utils import MAXNAMELEN, is_valid_name_component

if TYPE_CHECKING:
    from middlewared.main import Middleware

logger = logging.getLogger(__name__)

__all__ = ["resolve_dataset_path"]


def resolve_dataset_path(path: str, middleware: Middleware | None = None) -> tuple[str, str] | tuple[None, None]:
    """
    Resolve a filesystem path to the ZFS dataset that holds it and the path within that dataset.

    The holder is the deepest filesystem whose mountpoint contains the path, whether or not it is mounted:

    1. **Mounted datasets**: statx + statmount name the dataset mounted at or above the path. Where the path does
       not exist yet, its nearest existing ancestor is used. A bind mount answers with the dataset it shows part of.
    2. **Unmounted datasets**: a locked, ``canmount=noauto`` or not yet mounted child of that dataset holds the
       path instead where its mountpoint lies between the mount and the path. Where none of the pool is mounted,
       as when its root dataset is locked, the pool root and its children are looked for below ``/mnt``. Datasets
       are looked up by the names the path's components give them, so an unmounted dataset whose mountpoint was
       set to point there from elsewhere in the tree is not found.

    Args:
        path: Absolute filesystem path to resolve (e.g., '/mnt/tank/share/data')
        middleware: Middleware instance, required to find unmounted datasets

    Returns:
        ('pool/dataset', 'relative/path') if resolved
        (None, None) if no data pool dataset holds the path: it is reached through a symlink, is in a snapshot or
        another filesystem, or its pool is not imported
    """
    path = os.path.normpath(path)
    if (mntinfo := _nearest_mount(path)) is None:
        return None, None

    dataset = mntinfo.sb_source
    mnt_point = mntinfo.mnt_point or ""
    if mnt_point.startswith("/mnt/"):
        if mntinfo.fs_type != "zfs" or not dataset or "@" in dataset:
            logger.debug("%s: not on a data pool's ZFS mount", path)
            return None, None
        relative_path = os.path.relpath(path, mnt_point)
        if (mnt_root := mntinfo.mnt_root) and mnt_root != "/":
            # A bind mount shows a directory of its dataset, so the path within the dataset starts there
            relative_path = os.path.normpath(os.path.join(mnt_root.lstrip("/"), relative_path))
            return dataset, "" if relative_path == "." else relative_path
    elif path.startswith("/mnt/"):
        # The mount found is the one holding /mnt itself, so the path's pool root is not mounted
        dataset, mnt_point, relative_path = "", "/mnt", os.path.relpath(path, "/mnt")
    else:
        logger.debug("%s: not below /mnt", path)
        return None, None

    if relative_path == ".":
        return dataset, ""
    if middleware is not None and (holder := _unmounted_holder(path, dataset, mnt_point, relative_path, middleware)):
        return holder
    return (dataset, relative_path) if dataset else (None, None)


def _nearest_mount(path: str) -> truenas_os.StatmountResult | None:
    """Find the mount holding a path, or its nearest existing ancestor where the path does not exist.

    Args:
        path: Normalized absolute path

    Returns:
        The mount's statmount result, or None where the path cannot be opened, as through a symlink
    """
    existing = path
    while True:
        try:
            fd = truenas_os.openat2(existing, os.O_RDONLY, resolve=truenas_os.RESOLVE_NO_SYMLINKS)
            try:
                stx = truenas_os.statx(
                    "",
                    dir_fd=fd,
                    flags=truenas_os.AT_EMPTY_PATH,
                    mask=truenas_os.STATX_BASIC_STATS | truenas_os.STATX_MNT_ID_UNIQUE
                )
            finally:
                os.close(fd)
            return truenas_os.statmount(
                stx.stx_mnt_id,
                mask=(
                    truenas_os.STATMOUNT_MNT_POINT |
                    truenas_os.STATMOUNT_MNT_ROOT |
                    truenas_os.STATMOUNT_FS_TYPE |
                    truenas_os.STATMOUNT_SB_SOURCE
                )
            )
        except FileNotFoundError:
            if (parent := os.path.dirname(existing)) == existing:
                return None
            existing = parent
        except Exception as e:
            logger.debug("%s: unable to stat: %s", path, e)
            return None


def _unmounted_holder(
    path: str, dataset: str, mountpoint: str, relative_path: str, middleware: Middleware
) -> tuple[str, str] | None:
    """Find the deepest dataset below the one mounted at `mountpoint` that would mount between it and `path`.

    Args:
        path: The path being resolved
        dataset: The dataset mounted at `mountpoint`, or "" where `mountpoint` is /mnt, above every pool root
        mountpoint: Where `dataset` is mounted
        relative_path: `path` relative to `mountpoint`
        middleware: Middleware instance

    Returns:
        The dataset and the path within it, or None where no such dataset exists
    """
    candidates: dict[str, str] = {}
    name, directory = dataset, mountpoint
    for component in relative_path.split("/"):
        name = f"{name}/{component}" if name else component
        directory = os.path.join(directory, component)
        if component in (".", "..") or not is_valid_name_component(component) or len(name) > MAXNAMELEN:
            break
        candidates[name] = directory
    if not candidates:
        return None

    try:
        found = middleware.call_sync2(
            middleware.services.zfs.resource.list_impl,
            ZFSResourceQuery(paths=list(candidates), properties=["mountpoint", "canmount"]),
        )
    except Exception as e:
        logger.debug("%s: unable to look up the datasets below %s: %s", path, mountpoint, e)
        return None

    holder = None
    for ds in found:
        props = ds["properties"]
        if (
            ds["type"] == "FILESYSTEM"
            and props["canmount"]["raw"] != "off"
            and props["mountpoint"]["raw"] == candidates[ds["name"]]
            and (holder is None or len(ds["name"]) > len(holder))
        ):
            holder = ds["name"]

    if holder is None:
        return None
    relative_path = os.path.relpath(path, candidates[holder])
    return holder, "" if relative_path == "." else relative_path
