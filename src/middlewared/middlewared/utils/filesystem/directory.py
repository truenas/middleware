# Single-level directory listing built on top of
# ``truenas_os.iter_filesystem_contents``.  Used by ``filesystem.listdir`` and
# the various ``directory_is_empty`` callers.
#
# NOTE: tests for these utils live in tests/unit/test_directory.py

from __future__ import annotations

from collections.abc import Iterator
import enum
import errno
import os
from typing import Any

import truenas_os

from .acl import acl_is_present
from .attrs import fget_zfs_file_attributes, zfs_attributes_dump
from .constants import FileType
from .stat_x import StatxAttr, StatxEtype
from .utils import get_mount_info_for_path, path_in_ctldir


class DirectoryRequestMask(enum.IntFlag):
    """
    Bitmask controlling which optional metadata fields are populated for each
    yielded entry.  Omitting bits avoids the corresponding syscall(s) per entry.

    ACL       - boolean for whether the entry has an ACL (uses listxattr)
    CTLDIR    - boolean for whether the entry is in a ZFS ctldir
    REALPATH  - resolved (symlink-followed) path
    XATTRS    - list of extended attribute names
    ZFS_ATTRS - list of ZFS file attribute names; None for non-ZFS entries

    NOTE: changes here should be reflected in the ``test_listdir_request_mask``
    API test.
    """
    ACL = enum.auto()
    CTLDIR = enum.auto()
    REALPATH = enum.auto()
    XATTRS = enum.auto()
    ZFS_ATTRS = enum.auto()


ALL_ATTRS = (
    DirectoryRequestMask.ACL
    | DirectoryRequestMask.CTLDIR
    | DirectoryRequestMask.REALPATH
    | DirectoryRequestMask.XATTRS
    | DirectoryRequestMask.ZFS_ATTRS
)


def _etype(item: truenas_os.IterInstance) -> str:
    if item.isdir:
        return StatxEtype.DIRECTORY.name
    if item.islnk:
        return StatxEtype.SYMLINK.name
    if item.isreg:
        return StatxEtype.FILE.name
    return StatxEtype.OTHER.name


def _statx_attr_names(stx_attributes: int) -> list[str]:
    return [a.name for a in StatxAttr if stx_attributes & a.value and a.name is not None]


def _zfs_attrs_for(fd: int) -> list[str] | None:
    try:
        return zfs_attributes_dump(fget_zfs_file_attributes(fd))
    except OSError as e:
        # ENOTTY/EINVAL: not a ZFS filesystem.  Match historical None sentinel.
        if e.errno in (errno.ENOTTY, errno.EINVAL):
            return None
        raise


def _build_entry(
    parent_path: str,
    item: truenas_os.IterInstance,
    etype: str,
    mask: DirectoryRequestMask,
) -> dict[str, Any] | None:
    """
    Render a single iter_filesystem_contents item as a listdir-shaped dict.

    Symlinks are followed for stat/xattr/zfs metadata to match the historical
    listdir contract (size/mode/etc reflect the symlink target).  A broken
    symlink — one whose follow-statx fails with ``FileNotFoundError`` — is
    skipped by returning ``None``.
    """
    item_path = os.path.join(parent_path, item.name)

    if item.islnk:
        # iter_filesystem_contents gives us O_PATH on the symlink itself.
        # Follow the link (path-based) so stat / xattr / zfs reflect the target.
        try:
            st = truenas_os.statx(
                item_path,
                mask=truenas_os.STATX_BASIC_STATS | truenas_os.STATX_BTIME | truenas_os.STATX_MNT_ID_UNIQUE,
            )
        except FileNotFoundError:
            return None
        meta_fd: int | None = None
    else:
        st = item.statxinfo
        meta_fd = item.fd

    attributes = _statx_attr_names(st.stx_attributes)

    realpath = os.path.realpath(item_path) if mask & DirectoryRequestMask.REALPATH else None

    if mask & (DirectoryRequestMask.XATTRS | DirectoryRequestMask.ACL):
        try:
            xattr_list = os.listxattr(meta_fd) if meta_fd is not None else os.listxattr(item_path)
        except OSError:
            xattr_list = []
    else:
        xattr_list = None

    xattrs = xattr_list if mask & DirectoryRequestMask.XATTRS else None
    acl = acl_is_present(xattr_list) if mask & DirectoryRequestMask.ACL else None

    if mask & DirectoryRequestMask.ZFS_ATTRS:
        if meta_fd is not None:
            zfs_attrs = _zfs_attrs_for(meta_fd)
        else:
            try:
                tgt_fd = os.open(item_path, os.O_RDONLY)
            except OSError:
                zfs_attrs = None
            else:
                try:
                    zfs_attrs = _zfs_attrs_for(tgt_fd)
                finally:
                    os.close(tgt_fd)
    else:
        zfs_attrs = None

    is_ctldir = path_in_ctldir(item_path) if mask & DirectoryRequestMask.CTLDIR else None

    return {
        'name': item.name,
        'path': item_path,
        'realpath': realpath,
        'type': etype,
        'size': st.stx_size,
        'allocation_size': st.stx_blocks * 512,
        'mode': st.stx_mode,
        'acl': acl,
        'uid': st.stx_uid,
        'gid': st.stx_gid,
        'mount_id': st.stx_mnt_id,
        'is_mountpoint': StatxAttr.MOUNT_ROOT.name in attributes,
        'is_ctldir': is_ctldir,
        'attributes': attributes,
        'xattrs': xattrs,
        'zfs_attrs': zfs_attrs,
    }


def iter_listdir(
    path: str | os.PathLike,
    file_type: FileType | None = None,
    request_mask: DirectoryRequestMask | None = None,
) -> Iterator[dict[str, Any]]:
    """
    Yield single-level directory entries for ``path`` as listdir-shaped dicts.

    `file_type` - optional pre-filter restricting yielded entries to a single
    ``FileType``.

    `request_mask` - bitmask of optional metadata to populate.  ``None`` (the
    default) populates everything in :data:`ALL_ATTRS`; pass an explicit
    ``DirectoryRequestMask(0)`` to skip every optional fetch.
    """
    mnt, fs, rel = get_mount_info_for_path(path)
    mask = ALL_ATTRS if request_mask is None else request_mask
    want_type = FileType(file_type).name if file_type is not None else None
    parent_path = os.fspath(path)

    with truenas_os.iter_filesystem_contents(
        mnt, fs,
        relative_path=rel,
        include_symlinks=True,
    ) as it:
        for item in it:
            if item.isdir:
                # Single-level: never descend.
                it.skip()

            etype = _etype(item)
            if want_type is not None and etype != want_type:
                continue

            entry = _build_entry(parent_path, item, etype, mask)
            if entry is None:
                continue
            yield entry


def directory_is_empty(path: str | os.PathLike) -> bool:
    """
    Memory-efficient test for whether ``path`` is an empty directory.
    """
    return not any(iter_listdir(path, request_mask=DirectoryRequestMask(0)))
